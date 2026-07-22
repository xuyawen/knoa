from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.knowledge import CamelModel


class LoginIn(CamelModel):
    username: str
    password: str


class UserOut(CamelModel):
    id: str
    username: str
    display_name: str | None = None
    role: str                                   # admin | editor | viewer
    is_active: bool = True
    created_at: datetime | None = None
    preferred_model: str | None = None          # P8：偏好问答模型（透传进 ask 管线）
    tts_enabled: bool = False                   # P8：是否启用语音播报


class TokenOut(CamelModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreateIn(CamelModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str | None = None
    role: Literal["admin", "editor", "viewer"] = "viewer"


class UserUpdateIn(CamelModel):
    display_name: str | None = None
    role: Literal["admin", "editor", "viewer"] | None = None
    is_active: bool | None = None
    password: str | None = None


class ChangePasswordIn(CamelModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)
