"""系统设置：用户级偏好（preferred_model / tts_enabled）。

这些偏好由前端「设置」页读写，并驱动问答模型透传与语音播报开关。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db import User
from app.deps import get_db

router = APIRouter()


class SettingsOut(BaseModel):
    preferredModel: str | None = None
    ttsEnabled: bool = False


class SettingsUpdate(BaseModel):
    preferredModel: str | None = None
    ttsEnabled: bool | None = None


@router.get("/settings", response_model=SettingsOut)
async def get_settings(user: User = Depends(get_current_user)):
    return SettingsOut(preferredModel=user.preferred_model, ttsEnabled=bool(user.tts_enabled))


@router.put("/settings", response_model=SettingsOut)
async def update_settings(
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.preferredModel is not None:
        user.preferred_model = payload.preferredModel or None
    if payload.ttsEnabled is not None:
        user.tts_enabled = bool(payload.ttsEnabled)
    await db.commit()
    await db.refresh(user)
    return SettingsOut(preferredModel=user.preferred_model, ttsEnabled=bool(user.tts_enabled))
