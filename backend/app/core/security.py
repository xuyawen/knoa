"""Phase 2 RBAC 鉴权核心。

- JWT 用标准 HMAC-SHA256 手写实现，不依赖 PyJWT（venv 装不了第三方包）。
- 角色：admin(管用户+全部库) / editor(建库/传文档) / viewer(仅问答)。
- 库级权限：通过独立的 kb_permission 表实现单公司内部门间隔离。
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Awaitable, Callable

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import KBPermission, KnowledgeBase, User
from app.deps import get_db

_bearer = HTTPBearer(auto_error=False)

# 权限级别排序，数值越大权限越高
LEVEL_ORDER = {"view": 1, "edit": 2, "admin": 3}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_access_token(sub: str, username: str, role: str) -> str:
    header = {"alg": settings.JWT_ALGORITHM, "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": sub,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + settings.JWT_EXPIRE_MINUTES * 60,
    }
    seg_h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    seg_p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{seg_h}.{seg_p}".encode()
    sig = hmac.new(settings.JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    return f"{seg_h}.{seg_p}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> dict:
    try:
        seg_h, seg_p, sig = token.split(".")
    except ValueError:
        raise HTTPException(status_code=401, detail="无效令牌")
    signing_input = f"{seg_h}.{seg_p}".encode()
    expected = hmac.new(settings.JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_encode(expected), sig):
        raise HTTPException(status_code=401, detail="令牌签名无效")
    try:
        payload = json.loads(_b64url_decode(seg_p))
    except Exception:
        raise HTTPException(status_code=401, detail="令牌解析失败")
    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="令牌已过期")
    return payload


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    payload = decode_access_token(creds.credentials)
    user = await db.scalar(select(User).where(User.id == payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user


def require_roles(*roles: str) -> Callable[..., Awaitable[User]]:
    """依赖工厂：要求当前用户角色在 roles 内，否则 403。"""

    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return user

    return _dep


async def get_kb_permission_level(
    db: AsyncSession, kb_id: str, user: User
) -> str | None:
    """返回用户对某 KB 的最高权限级别；None 表示无权限。

    - admin 角色隐式拥有全部 KB 的 admin 级。
    - 若 KB 完全没有任何权限记录（遗留种子库），视为对全体已登录用户开放 view。
    - 若 KB 已有权限记录但当前用户不在其中，则返回 None（严格隔离）。
    """
    if user.role == "admin":
        return "admin"
    rows = (
        await db.execute(
            select(KBPermission).where(
                KBPermission.kb_id == kb_id, KBPermission.user_id == user.id
            )
        )
    ).scalars().all()
    if rows:
        return max(rows, key=lambda p: LEVEL_ORDER.get(p.level, 0)).level
    # 该用户无记录：判断 KB 是否处于"严格模式"（已有他人权限）
    any_perm = await db.scalar(
        select(KBPermission.id).where(KBPermission.kb_id == kb_id).limit(1)
    )
    if any_perm is None:
        # 遗留开放库（无任何权限记录）：对全体已登录用户开放，按角色授予
        return "edit" if user.role in ("admin", "editor") else "view"
    return None         # 严格库，当前用户未被授权


def require_kb_access(min_level: str = "view"):
    """依赖工厂：要求当前用户对路径中的 kb_id 拥有 >= min_level 的权限。"""

    async def _dep(
        kb_id: str,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> User:
        level = await get_kb_permission_level(db, kb_id, user)
        if level is None or LEVEL_ORDER.get(level, 0) < LEVEL_ORDER.get(min_level, 0):
            raise HTTPException(status_code=403, detail="无权访问该知识库")
        return user

    return _dep


async def get_accessible_kb_ids(db: AsyncSession, user: User) -> list[str]:
    """返回当前用户对 view+ 可见的全部 KB id（用于「未指定 KB 时」的检索范围限定）。

    - admin 角色：可见全部库；
    - 其余用户：在 kb_permission 中有记录者 + 遗留「开放库」（该库无任何权限记录）可见；
      严格隔离库（已有他人权限记录但自己不在其中）不可见。
    语义与 get_kb_permission_level 的「遗留开放库」规则保持一致。
    """
    if user.role == "admin":
        rows = (await db.execute(select(KnowledgeBase.id))).scalars().all()
        return [str(x) for x in rows]
    all_kb_ids = [
        str(x) for x in (await db.execute(select(KnowledgeBase.id))).scalars().all()
    ]
    user_perm_kbs = {
        str(r[0])
        for r in (
            await db.execute(
                select(KBPermission.kb_id).where(KBPermission.user_id == user.id)
            )
        ).all()
    }
    strict_kb_ids = {str(r[0]) for r in (await db.execute(select(KBPermission.kb_id))).all()}
    return [
        kb for kb in all_kb_ids
        if kb in user_perm_kbs or kb not in strict_kb_ids
    ]
