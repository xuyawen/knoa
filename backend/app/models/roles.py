from typing import Any

from pydantic import Field

from app.core.rbac import PERMISSION_KEYS
from app.models.knowledge import CamelModel


class RoleOut(CamelModel):
    id: str
    key: str
    name: str
    description: str | None = None
    is_builtin: bool
    sort_order: int
    permissions: list[str]


class RoleCreateIn(CamelModel):
    name: str = Field(..., min_length=1, max_length=50)
    key: str | None = Field(default=None, max_length=50)
    description: str | None = None
    permissions: list[str] = []


class RoleUpdateIn(CamelModel):
    name: str | None = None
    description: str | None = None


class RolePermissionsIn(CamelModel):
    permissions: list[str] = []


def validate_permissions(keys: list[str]) -> None:
    """校验权限 key 是否合法，非法则抛 ValueError。"""
    unknown = [k for k in keys if k not in PERMISSION_KEYS]
    if unknown:
        raise ValueError(f"未知权限: {', '.join(unknown)}")


def role_to_out(r: Any, permissions: list[str]) -> RoleOut:
    return RoleOut(
        id=str(r.id),
        key=r.key,
        name=r.name,
        description=r.description,
        is_builtin=r.is_builtin,
        sort_order=r.sort_order,
        permissions=permissions,
    )
