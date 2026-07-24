"""Phase 2 鉴权路由：登录、当前用户、用户管理（仅 admin）。"""
import uuid

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    decode_access_token,
    extract_token,
    get_current_user,
    get_role_permissions,
    require_permission,
    revoke_token,
)
from app.core.rbac import Perm
from app.db import ChatSession, KBPermission, Memory, Role, User
from app.deps import get_db, get_redis
from app.models.operation_log import record_operation
from app.config import settings
from app.models.auth import (
    ChangePasswordIn,
    LoginIn,
    TokenOut,
    UserCreateIn,
    UserOut,
    UserUpdateIn,
)
from app.models.common import PaginatedOut
from app.core.pagination import paginate

router = APIRouter()

# 登录时序侧信道防护用的占位哈希：用户不存在时也跑一次等效 PBKDF2 校验，
# 使「用户存在/不存在」「密码对错」路径响应时间趋同，防止攻击者通过耗时枚举有效用户名。
DUMMY_HASH = User.hash_password("knoa-timing-dummy")


async def _resolve_role_id(db: AsyncSession, role_id: str) -> uuid.UUID:
    """校验 role_id 是否存在，不存在则 400。"""
    rid = uuid.UUID(role_id) if isinstance(role_id, str) else role_id
    role = await db.scalar(select(Role).where(Role.id == rid))
    if role is None:
        raise HTTPException(status_code=400, detail="角色不存在")
    return rid


def _to_out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        username=u.username,
        display_name=u.display_name,
        role=u.role,
        role_id=str(u.role_id),
        is_active=u.is_active,
        created_at=u.created_at,
        preferred_model=u.preferred_model,
        tts_enabled=u.tts_enabled,
        email=u.email,
        department=u.department,
        employee_id=u.employee_id,
    )


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(settings.COOKIE_NAME, path="/")


logger = logging.getLogger("knoa.auth")

LOGIN_RATE_LIMIT = 10        # 每窗口最大登录尝试次数
LOGIN_RATE_WINDOW = 60       # 滑动窗口大小（秒）


async def login_rate_limit(request: Request) -> None:
    """登录接口限流：按客户端 IP 滑动窗口限制，防暴力破解。

    Redis 不可用时放行（不阻断登录），仅告警，避免限流组件自身成为单点。
    """
    fwd = request.headers.get("X-Forwarded-For", "")
    client_ip = fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    key = f"knoa:login:rl:{client_ip}"
    try:
        r = get_redis().redis
        cnt = await r.incr(key)
        if cnt == 1:
            await r.expire(key, LOGIN_RATE_WINDOW)
        if cnt > LOGIN_RATE_LIMIT:
            raise HTTPException(status_code=429, detail="登录尝试过于频繁，请稍后再试")
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, skip rate limit if redis unavailable)
        logger.warning("login rate limit skipped (redis unavailable)")


@router.post("/auth/login", response_model=TokenOut, dependencies=[Depends(login_rate_limit)])
async def login(payload: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.username == payload.username))
    # 时序侧信道防护：无论用户是否存在，都执行一次恒定耗时的 PBKDF2 校验，
    # 使「存在/不存在」「密码对错」路径响应时间趋同，防止攻击者通过耗时枚举有效用户名。
    if user is None:
        User.verify_password(payload.password, DUMMY_HASH)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.verify_password(payload.password) or not user.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(str(user.id), user.username, user.role)
    _set_auth_cookie(response, token)
    await record_operation(db, user, "login")
    return TokenOut(access_token=token, user=_to_out(user))


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    _clear_auth_cookie(response)
    # 服务端吊销：把当前 token 的 jti 加入黑名单，使其立即失效（即便 cookie 未清除）
    raw = extract_token(request)
    if raw:
        try:
            payload = decode_access_token(raw)
            jti = payload.get("jti")
            if jti:
                ttl = int(payload.get("exp", 0)) - int(time.time())
                await revoke_token(jti, ttl)
        except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, skip server-side revoke if token undecodable)
            pass
    return {"detail": "已退出登录"}


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return _to_out(user)


@router.put("/auth/change-password")
async def change_password(
    payload: ChangePasswordIn,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """用户自行修改密码（验证旧密码 + 设置新密码）。"""
    if not current.verify_password(payload.old_password):
        raise HTTPException(status_code=400, detail="原密码不正确")
    if payload.old_password == payload.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")
    # 重新加载最新状态，避免 stale ORM 对象
    fresh = await db.scalar(select(User).where(User.id == current.id))
    if fresh is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    fresh.password_hash = User.hash_password(payload.new_password)
    await db.commit()
    return {"detail": "密码修改成功"}


@router.get("/auth/users", response_model=PaginatedOut[UserOut])
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    role: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    """用户列表分页，支持角色/用户名/显示名搜索过滤。仅用户管理员可见。"""
    stmt = select(User).order_by(User.created_at)
    if role:
        # role 过滤支持角色 key（如 'admin'）或角色 id
        role_obj = await db.scalar(
            select(Role).where((Role.key == role) | (Role.id == role))
        )
        if role_obj is None:
            return {
                "items": [], "total": 0, "page": page, "page_size": size,
                "pages": 1,
            }
        stmt = stmt.where(User.role_id == role_obj.id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(User.username.ilike(like), User.display_name.ilike(like)))
    rows, total = await paginate(db, stmt, page=page, page_size=size)
    pages = max(1, (total + size - 1) // size) if total else 1
    return {
        "items": [_to_out(r[0]) for r in rows],
        "total": total,
        "page": page,
        "page_size": size,
        "pages": pages,
    }


@router.post("/auth/users", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreateIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    if await db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=409, detail="用户名已存在")
    role_id = await _resolve_role_id(db, payload.role_id)
    u = User(
        id=uuid.uuid4(),
        username=payload.username,
        password_hash=User.hash_password(payload.password),
        display_name=payload.display_name,
        role_id=role_id,
        email=payload.email,
        department=payload.department,
        employee_id=payload.employee_id,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return _to_out(u)


@router.patch("/auth/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UserUpdateIn,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    u = await db.scalar(select(User).where(User.id == user_id))
    if u is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    # ponytail: 本人可改自己的 display_name；改他人或改角色/状态/密码需用户管理员
    is_self = u.id == current.id
    if not is_self and not await _is_admin(current, db):
        raise HTTPException(status_code=403, detail="无权修改其他用户")
    privileged = payload.role_id is not None or payload.is_active is not None or payload.password
    if privileged and not await _is_admin(current, db):
        raise HTTPException(status_code=403, detail="无权修改该字段")
    # 保护最后一个 admin：降级或停用当前 admin 时，必须仍有其他启用 admin
    if await _is_admin(current, db):
        demoting = payload.role_id is not None and payload.role_id != str(u.role_id)
        disabling = payload.is_active is False
        if u.role == "admin" and (demoting or disabling):
            other_active_admins = await db.scalar(
                select(func.count())
                .select_from(User)
                .join(Role, Role.id == User.role_id)
                .where(Role.key == "admin", User.is_active.is_(True), User.id != u.id)
            )
            if not other_active_admins:
                raise HTTPException(status_code=400, detail="不能降级或停用最后一个管理员")
    if payload.display_name is not None:
        u.display_name = payload.display_name
    # 档案字段（邮箱/部门/工号）本人与 admin 均可改，不算特权字段
    if payload.email is not None:
        u.email = payload.email
    if payload.department is not None:
        u.department = payload.department
    if payload.employee_id is not None:
        u.employee_id = payload.employee_id
    if await _is_admin(current, db):
        if payload.role_id is not None:
            u.role_id = await _resolve_role_id(db, payload.role_id)
        if payload.is_active is not None:
            u.is_active = payload.is_active
        if payload.password:
            u.password_hash = User.hash_password(payload.password)
    await db.commit()
    await db.refresh(u)
    return _to_out(u)


async def _is_admin(user: User, db: AsyncSession) -> bool:
    """通过权限判断是否为用户管理员（role=admin 的内置角色拥有 user_manage）。"""
    perms = await get_role_permissions(db, user.role_id)
    return Perm.USER_MANAGE in perms


@router.delete("/auth/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    if str(current.id) == user_id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    u = await db.scalar(select(User).where(User.id == user_id))
    if u is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if u.role == "admin":
        other_admins = await db.scalar(
            select(func.count())
            .select_from(User)
            .join(Role, Role.id == User.role_id)
            .where(Role.key == "admin", User.id != u.id)
        )
        if not other_admins:
            raise HTTPException(status_code=400, detail="不能删除最后一个管理员")
    # 级联清理：kb_permission.user_id / memory.user_id 都是指向 app_user 的外键，
    # 不先删这些子记录，PostgreSQL 会直接拒绝删除用户（外键约束 → 500）。
    # ChatSession.user_id 是无外键约束的普通字符串列，这里一并清理孤儿会话。
    await db.execute(delete(KBPermission).where(KBPermission.user_id == u.id))
    await db.execute(delete(Memory).where(Memory.user_id == u.id))
    await db.execute(delete(ChatSession).where(ChatSession.user_id == str(u.id)))
    await db.delete(u)
    await db.commit()
