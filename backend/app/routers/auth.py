"""Phase 2 鉴权路由：登录、当前用户、用户管理（仅 admin）。"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    get_current_user,
    require_roles,
)
from app.db import User
from app.deps import get_db
from app.models.auth import (
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
    )


@router.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.username == payload.username))
    if user is None or not user.verify_password(payload.password) or not user.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(str(user.id), user.username, user.role)
    return TokenOut(access_token=token, user=_to_out(user))


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return _to_out(user)


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
    await db.delete(u)
    await db.commit()
