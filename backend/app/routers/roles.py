"""角色管理 API：角色 CRUD + 权限分配。仅用户管理员可见。"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import PERMISSION_KEYS
from app.core.security import get_current_user, require_permission
from app.core.rbac import Perm
from app.db import Role, RolePermission, User
from app.deps import get_db
from app.models.roles import (
    RoleCreateIn,
    RoleOut,
    RolePermissionsIn,
    RoleUpdateIn,
    role_to_out,
    validate_permissions,
)

router = APIRouter()


async def _role_permissions(db: AsyncSession, role_id: uuid.UUID) -> list[str]:
    rows = (
        await db.execute(
            select(RolePermission.permission_key)
            .where(RolePermission.role_id == role_id)
            .order_by(RolePermission.permission_key)
        )
    ).scalars().all()
    return list(rows)


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    """列出全部角色及其权限集合（角色管理矩阵数据源）。"""
    roles = (
        await db.execute(select(Role).order_by(Role.sort_order, Role.created_at))
    ).scalars().all()
    out = []
    for r in roles:
        out.append(role_to_out(r, await _role_permissions(db, r.id)))
    return out


@router.post("/roles", response_model=RoleOut, status_code=201)
async def create_role(
    payload: RoleCreateIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    """新建自定义角色（is_builtin=False）。key 可指定，缺省自动生成。"""
    try:
        validate_permissions(payload.permissions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    key = payload.key
    if not key:
        key = f"custom_{uuid.uuid4().hex[:8]}"
    key = key.strip()
    if not (1 <= len(key) <= 50):
        raise HTTPException(status_code=400, detail="角色 key 长度需在 1-50 之间")
    if await db.scalar(select(Role).where(Role.key == key)):
        raise HTTPException(status_code=409, detail="角色 key 已存在")

    max_order = await db.scalar(select(func.max(Role.sort_order)).select_from(Role))
    role = Role(
        id=uuid.uuid4(),
        key=key,
        name=payload.name.strip(),
        description=payload.description,
        is_builtin=False,
        sort_order=(max_order or 0) + 1,
    )
    db.add(role)
    for pk in payload.permissions:
        db.add(RolePermission(role_id=role.id, permission_key=pk))
    await db.commit()
    await db.refresh(role)
    return role_to_out(role, payload.permissions)


@router.put("/roles/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: str,
    payload: RoleUpdateIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    """编辑角色名称/描述（内置角色也允许改名称与描述，但不允许改 key）。"""
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    if payload.name is not None:
        role.name = payload.name.strip()
    if payload.description is not None:
        role.description = payload.description
    await db.commit()
    await db.refresh(role)
    return role_to_out(role, await _role_permissions(db, role.id))


@router.put("/roles/{role_id}/permissions", response_model=RoleOut)
async def set_role_permissions(
    role_id: str,
    payload: RolePermissionsIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    """批量设置某角色的权限集合（全量覆盖）。内置/自定义角色均可。"""
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    try:
        validate_permissions(payload.permissions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.execute(
        RolePermission.__table__.delete().where(RolePermission.role_id == role.id)
    )
    for pk in payload.permissions:
        if pk in PERMISSION_KEYS:
            db.add(RolePermission(role_id=role.id, permission_key=pk))
    await db.commit()
    await db.refresh(role)
    return role_to_out(role, payload.permissions)


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    """删除自定义角色。内置角色不可删；仍有用户绑定时不可删。"""
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_builtin:
        raise HTTPException(status_code=400, detail="内置角色不可删除")
    user_count = await db.scalar(
        select(func.count()).select_from(User).where(User.role_id == role.id)
    )
    if user_count:
        raise HTTPException(
            status_code=400, detail=f"该角色下仍有 {user_count} 名用户，无法删除"
        )
    await db.execute(
        RolePermission.__table__.delete().where(RolePermission.role_id == role.id)
    )
    await db.delete(role)
    await db.commit()
