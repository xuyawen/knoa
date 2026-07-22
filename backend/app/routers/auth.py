"""Phase 2 鉴权路由：登录、当前用户、用户管理（仅 admin）。"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    get_current_user,
    require_roles,
)
from app.db import ChatSession, KBPermission, Memory, User
from app.deps import get_db
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

router = APIRouter()


def _to_out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        username=u.username,
        display_name=u.display_name,
        role=u.role,
        is_active=u.is_active,
        created_at=u.created_at,
        preferred_model=u.preferred_model,
        tts_enabled=u.tts_enabled,
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


@router.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.username == payload.username))
    if user is None or not user.verify_password(payload.password) or not user.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(str(user.id), user.username, user.role)
    _set_auth_cookie(response, token)
    await record_operation(db, user, "login")
    return TokenOut(access_token=token, user=_to_out(user))


@router.post("/auth/logout")
async def logout(response: Response):
    _clear_auth_cookie(response)
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


@router.get("/auth/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    rows = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
    return [_to_out(u) for u in rows]


@router.post("/auth/users", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreateIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    if await db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=409, detail="用户名已存在")
    u = User(
        id=uuid.uuid4(),
        username=payload.username,
        password_hash=User.hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
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
    _: User = Depends(require_roles("admin")),
):
    u = await db.scalar(select(User).where(User.id == user_id))
    if u is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 保护最后一个 admin：降级或停用当前 admin 时，必须仍有其他启用 admin
    demoting = payload.role is not None and payload.role != "admin"
    disabling = payload.is_active is False
    if u.role == "admin" and (demoting or disabling):
        other_active_admins = await db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == "admin", User.is_active.is_(True), User.id != u.id)
        )
        if not other_active_admins:
            raise HTTPException(status_code=400, detail="不能降级或停用最后一个管理员")
    if payload.display_name is not None:
        u.display_name = payload.display_name
    if payload.role is not None:
        u.role = payload.role
    if payload.is_active is not None:
        u.is_active = payload.is_active
    if payload.password:
        u.password_hash = User.hash_password(payload.password)
    await db.commit()
    await db.refresh(u)
    return _to_out(u)


@router.delete("/auth/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_roles("admin")),
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
            .where(User.role == "admin", User.id != u.id)
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
