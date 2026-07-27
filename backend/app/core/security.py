"""Phase 2 RBAC 鉴权核心。

- JWT 用标准 HMAC-SHA256 手写实现，不依赖 PyJWT（venv 装不了第三方包）。
- 角色：admin(管用户+全部库) / editor(建库/传文档) / viewer(仅问答)。
- 库级权限：通过独立的 kb_permission 表实现单公司内部门间隔离。
"""
import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rbac import PERMISSION_KEYS, Perm
from app.db import Department, Document, KBPermission, KnowledgeBase, RolePermission, User
from app.deps import get_db, get_redis

logger = logging.getLogger("knoa.security")

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
        "jti": uuid.uuid4().hex,
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
        raise HTTPException(status_code=401, detail="无效令牌") from None
    # ponytail: 显式校验 header.alg，纵深防御 alg 混淆攻击（如 alg=none 伪造令牌）
    try:
        header = json.loads(_b64url_decode(seg_h))
    except Exception:  # noqa: BLE001  (intentional catch-all: malformed header → 401)
        raise HTTPException(status_code=401, detail="令牌解析失败") from None
    if header.get("alg") != settings.JWT_ALGORITHM:
        raise HTTPException(status_code=401, detail="不支持的签名算法") from None
    signing_input = f"{seg_h}.{seg_p}".encode()
    expected = hmac.new(settings.JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_encode(expected), sig):
        raise HTTPException(status_code=401, detail="令牌签名无效")
    try:
        payload = json.loads(_b64url_decode(seg_p))
    except Exception:  # noqa: BLE001  (intentional catch-all: any token payload parse failure → 401)
        raise HTTPException(status_code=401, detail="令牌解析失败") from None
    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="令牌已过期")
    return payload


async def revoke_token(jti: str, ttl: int) -> None:
    """注销时把 jti 加入 Redis 黑名单，TTL=剩余有效期；Redis 不可用时静默降级。"""
    try:
        await get_redis().redis.set(f"knoa:revoked:{jti}", "1", ex=max(int(ttl), 1))
    except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, degrade silently if redis unavailable)
        logger.warning("revoke token failed (redis unavailable?)")


async def is_token_revoked(jti: str) -> bool:
    """检查 jti 是否已被注销。

    Redis 不可用时：生产环境 fail-closed（视为已吊销，避免已注销令牌
    在黑名单不可查期间复活）；开发/测试环境 fail-open 保证可用性。
    与 login_rate_limit「生产 Redis 是硬依赖」的策略保持一致。
    """
    if not jti:
        return False
    try:
        return await get_redis().redis.exists(f"knoa:revoked:{jti}") == 1
    except Exception:  # noqa: BLE001  (intentional catch-all: redis unavailable → fail-closed in prod, fail-open in dev/test)
        if settings.APP_ENV == "production":
            logger.warning("revocation check unavailable, fail-closed (prod)")
            return True
        return False


async def revoke_user_tokens_before(user_id: str) -> None:
    """改密后按用户吊销：记录时间戳，iat 早于该时刻的令牌全部失效。

    TTL = 令牌最长寿命：更早的令牌届时已自然过期，键可安全消失。
    Redis 不可用时静默降级（与 revoke_token 一致）。
    """
    try:
        await get_redis().redis.set(
            f"knoa:pwdrevoked:{user_id}",
            str(int(time.time())),
            ex=settings.JWT_EXPIRE_MINUTES * 60,
        )
    except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, degrade silently if redis unavailable)
        logger.warning("revoke user tokens failed (redis unavailable?)")


async def is_token_stale(user_id: str, iat: int) -> bool:
    """改密吊销检查：签发时间早于该用户最近一次改密时刻的令牌视为失效。"""
    try:
        v = await get_redis().redis.get(f"knoa:pwdrevoked:{user_id}")
        return v is not None and iat < int(v)
    except Exception:  # noqa: BLE001  (intentional catch-all: same fail-closed/fail-open policy as is_token_revoked)
        return settings.APP_ENV == "production"


def extract_token(request: Request) -> str | None:
    """从 HttpOnly Cookie 或 Authorization 头取令牌（Cookie 优先，防 XSS 窃取）。

    前端走 Cookie（JS 读不到）；API / 压测客户端仍可带 Authorization 头。
    """
    cookie = request.cookies.get(settings.COOKIE_NAME)
    if cookie:
        return cookie
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):].strip()
    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    payload = decode_access_token(token)
    # 防御性取值：缺 sub 的畸形令牌应明确 401，而非 KeyError 兑成 500
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="无效令牌")
    if await is_token_revoked(payload.get("jti", "")):
        raise HTTPException(status_code=401, detail="令牌已吊销")
    # 改密吊销：密码修改后，此前签发的全部令牌立即失效
    if await is_token_stale(sub, int(payload.get("iat", 0))):
        raise HTTPException(status_code=401, detail="凭证已失效，请重新登录")
    user = await db.scalar(select(User).where(User.id == sub))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user


async def get_role_permissions(db: AsyncSession, role_id: uuid.UUID) -> set[str]:
    """返回某角色拥有的全部 permission_key 集合。"""
    rows = (
        await db.execute(
            select(RolePermission.permission_key).where(RolePermission.role_id == role_id)
        )
    ).scalars().all()
    return set(rows)


async def _is_kb_super_admin(db: AsyncSession, user: User) -> bool:
    """内置 admin 角色（拥有 user_manage 权限）隐式拥有全部知识库的 admin 级权限。

    RBAC 重构后 User.role 字符串列已废弃，改用 role_id → 角色权限集合判定，
    与 routers/auth.py 的 _is_admin 保持一致。
    """
    perms = await get_role_permissions(db, user.role_id)
    return Perm.USER_MANAGE in perms


def require_permission(permission: str) -> Callable[..., Awaitable[User]]:
    """依赖工厂：要求当前用户所属角色拥有指定权限，否则 403。"""

    async def _dep(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if permission not in PERMISSION_KEYS:
            raise HTTPException(status_code=500, detail=f"未知权限: {permission}")
        perms = await get_role_permissions(db, user.role_id)
        if permission not in perms:
            raise HTTPException(status_code=403, detail="权限不足")
        return user

    return _dep


async def get_kb_permission_level(
    db: AsyncSession, kb_id: str, user: User
) -> str | None:
    """返回用户对某 KB 的最高权限级别；None 表示无权限。

    - admin 角色（_is_kb_super_admin）隐式拥有全部 KB 的 admin 级。
    - 若 KB 完全没有任何权限记录（遗留种子库），视为对全体已登录用户开放 view。
    - 若 KB 已有权限记录但当前用户不在其中，则返回 None（严格隔离）。
    """
    if await _is_kb_super_admin(db, user):
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
        # 遗留开放库（无任何权限记录）：仅隐式开放 view（只读）。
        # 写操作（edit/admin）必须显式授权——否则"建库忘加权限记录"会让所有
        # DOC_EDIT 角色用户都能改/删全库文档（含他人 private），叠加文档级
        # scope 后这个坑更危险。超管仍由 _is_kb_super_admin 走 admin 不受影响。
        return "view"
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
    语义与 get_kb_permission_level 的「遗留开放库」规则保持一致；
    非 admin 分支用单条 EXISTS 查询完成（原先拆成 3 次全量查询 + 内存集合运算）。
    """
    if await _is_kb_super_admin(db, user):
        rows = (await db.execute(select(KnowledgeBase.id))).scalars().all()
        return [str(x) for x in rows]
    user_perm = (
        select(KBPermission.id)
        .where(KBPermission.kb_id == KnowledgeBase.id, KBPermission.user_id == user.id)
        .exists()
    )
    any_perm = select(KBPermission.id).where(KBPermission.kb_id == KnowledgeBase.id).exists()
    rows = (
        await db.execute(select(KnowledgeBase.id).where(user_perm | ~any_perm))
    ).scalars().all()
    return [str(x) for x in rows]


# ---------------------------------------------------------------------------
# 文档级 scope 可见性（scope 补全）
# ---------------------------------------------------------------------------
# 非 admin 用户可见 public；department 需按部门子树判定（不在此列），private 仅上传者本人可见。
SCOPE_PUBLIC_LIKE: tuple[str, ...] = ("public",)
SCOPE_PRIVATE = "private"
SCOPE_DEPARTMENT = "department"


@dataclass(frozen=True)
class ScopeContext:
    """检索/列表的文档级可见性上下文。

    is_admin（超级管理员或该库 KB admin）→ 可见全部，跳过 scope 过滤；
    其余用户仅可见 public-like、自己的 private、以及命中可见部门子树的 department 文档。
    """

    user_id: str
    is_admin: bool
    # 用户可见的部门 id 集合（本人部门 + 所有后代部门，str 形式）；department 文档命中此集合才可见
    visible_dept_ids: frozenset[str] = frozenset()


async def is_super_admin(db: AsyncSession, user: User) -> bool:
    """超级管理员（拥有 user_manage 权限）公开判定，供检索/列表注入 ScopeContext。"""
    return await _is_kb_super_admin(db, user)


async def compute_visible_dept_ids(db: AsyncSession, user: User) -> frozenset[str]:
    """计算用户可见的部门 id 集合：本人部门 + 所有后代部门（部门树向下递归）。

    无部门用户返回空集（看不到任何 department 文档）。一次全量拉取部门（量小），
    内存 BFS 展开子树，避免递归 SQL。
    """
    if user.department_id is None:
        return frozenset()
    rows = (await db.execute(select(Department.id, Department.parent_id))).all()
    children: dict[uuid.UUID | None, list[uuid.UUID]] = {}
    for did, pid in rows:
        children.setdefault(pid, []).append(did)
    visible: set[uuid.UUID] = set()
    stack = [user.department_id]
    while stack:
        cur = stack.pop()
        if cur in visible:
            continue
        visible.add(cur)
        stack.extend(children.get(cur, []))
    return frozenset(str(d) for d in visible)


def doc_scope_clause(user: User, is_admin: bool, visible_dept_ids: frozenset[str] = frozenset()):
    """返回 SQLAlchemy 条件：当前用户可见的文档 scope 范围；is_admin → None（不限制）。

    用于 list_documents / search_docs / 文档详情的强制可见性过滤。
    普通用户：public 全可见 + private 仅本人 + department 命中可见部门子树。
    """
    if is_admin:
        return None
    clauses = [
        Document.scope.in_(SCOPE_PUBLIC_LIKE),
        and_(Document.scope == SCOPE_PRIVATE, Document.uploader_id == user.id),
    ]
    if visible_dept_ids:
        dept_uuids = [uuid.UUID(d) for d in visible_dept_ids]
        clauses.append(
            and_(Document.scope == SCOPE_DEPARTMENT, Document.department_id.in_(dept_uuids))
        )
    return or_(*clauses)


def is_scope_visible(
    scope: str,
    uploader_id,
    ctx: ScopeContext | None,
    department_id: str | None = None,
) -> bool:
    """单个 chunk/文档的可见性判定（pgvector 检索分数掩码用，纯 Python）。

    与 doc_scope_clause 语义一致；uploader_id 可为 UUID 或 str，统一转 str 比较。
    ctx 为 None（内部任务/无用户上下文）或 admin → 全可见。
    department 文档：department_id 命中 ctx.visible_dept_ids 才可见。
    未知 scope 兜底放行（数据异常时宁可可见也不误杀，与 public 默认值一致）。
    """
    if ctx is None or ctx.is_admin:
        return True
    if scope in SCOPE_PUBLIC_LIKE:
        return True
    if scope == SCOPE_PRIVATE:
        return uploader_id is not None and str(uploader_id) == ctx.user_id
    if scope == SCOPE_DEPARTMENT:
        return bool(department_id) and str(department_id) in ctx.visible_dept_ids
    # 未知 scope：兜底放行（与 public 默认值一致，避免脏数据误杀），但打 warning 便于排查。
    # 权限系统理论上更该 fail-closed，这里权衡可用性选 fail-open + 告警（不再静默放过）。
    logger.warning(
        "is_scope_visible 遇到未知 scope=%r（uploader=%s），按 fail-open 放行", scope, uploader_id
    )
    return True


async def ensure_doc_scope_writable(db: AsyncSession, doc: Document, user: User) -> None:
    """写操作（删除/审核通过/驳回）的文档级 scope 校验，不可见 → 403。

    与读路径 get_document 的 scope 校验对称：先取库级权限定 admin，
    非 admin 再算部门子树并判 is_scope_visible。堵住"有库 edit 就能改/删
    别人 private 文档"的越权（读路径已拦，写路径补上）；admin 豁免。
    """
    level = await get_kb_permission_level(db, doc.kb_id, user)
    is_admin = level == "admin"
    dept_ids = frozenset() if is_admin else await compute_visible_dept_ids(db, user)
    if not is_scope_visible(
        doc.scope, doc.uploader_id,
        ScopeContext(str(user.id), is_admin, dept_ids),
        str(doc.department_id) if doc.department_id else None,
    ):
        raise HTTPException(status_code=403, detail="无权操作该文档")
