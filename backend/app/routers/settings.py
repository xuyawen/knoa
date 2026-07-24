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


# 模型配置偏好默认值（服务端真值，前端不再依赖 localStorage）。
# name(模型选择)单独走 preferred_model 列；其余 10 项走 model_prefs JSONB。
DEFAULT_MODEL_PREFS: dict = {
    "temp": 0.3,
    "topP": 0.9,
    "maxTokens": 2000,
    "topK": 5,
    "webSearch": True,
    "sourceCount": 5,
    "webProvider": "auto",
    "systemPrompt": "",
    "showThinking": True,
    "conciseMode": False,
}


class SettingsOut(BaseModel):
    preferredModel: str | None = None
    ttsEnabled: bool = False
    modelPrefs: dict = {}


class SettingsUpdate(BaseModel):
    preferredModel: str | None = None
    ttsEnabled: bool | None = None
    modelPrefs: dict | None = None


@router.get("/settings", response_model=SettingsOut)
async def get_settings(user: User = Depends(get_current_user)):
    stored = user.model_prefs or {}
    merged = {**DEFAULT_MODEL_PREFS, **stored}
    return SettingsOut(
        preferredModel=user.preferred_model,
        ttsEnabled=bool(user.tts_enabled),
        modelPrefs=merged,
    )


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
    if payload.modelPrefs is not None:
        # 信任边界：只收已知键，过滤前端可能误存的脏字段
        user.model_prefs = {
            k: payload.modelPrefs.get(k, DEFAULT_MODEL_PREFS[k])
            for k in DEFAULT_MODEL_PREFS
        }
    await db.commit()
    await db.refresh(user)
    merged = {**DEFAULT_MODEL_PREFS, **(user.model_prefs or {})}
    return SettingsOut(
        preferredModel=user.preferred_model,
        ttsEnabled=bool(user.tts_enabled),
        modelPrefs=merged,
    )
