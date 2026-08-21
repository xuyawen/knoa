"""系统设置：用户级偏好（preferred_model / tts_enabled）。

这些偏好由前端「设置」页读写，并驱动问答模型透传与语音播报开关。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, vision_llm_available
from app.core.security import get_current_user
from app.db import User
from app.deps import get_db

router = APIRouter()


# 模型配置偏好默认值（服务端真值，前端不再依赖 localStorage）。
# name(模型选择)单独走 preferred_model 列；其余走 model_prefs JSONB。
# ttsVoiceType：腾讯 TTS 音色（1002 温润女声 | 1004 成熟男声 | 1050 新闻女声）。
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
    "ttsVoiceType": 1002,
    "enterToSend": True,
}


class SettingsOut(BaseModel):
    preferredModel: str | None = None
    ttsEnabled: bool = False
    modelPrefs: dict = {}
    # 视觉问答是否可用（百炼端点已配置）；带图提问时后端自动路由视觉模型，
    # 与所选文本模型无关，前端据此 gating 图片上传
    chatVision: bool = False


class SettingsUpdate(BaseModel):
    preferredModel: str | None = None
    ttsEnabled: bool | None = None
    modelPrefs: dict | None = None


class SystemStatusOut(BaseModel):
    """后端运行配置概览（只读、非机密）：供「模型配置」页「当前状态」面板渲染。

    只暴露模型名 / 功能开关 / 密钥是否配置，绝不暴露密钥本身。
    """
    defaultModel: str               # 「系统默认」实际对应的 LLM 模型
    embeddingModel: str
    embeddingDim: int
    reranker: str                   # auto | cross-encoder | lexical-semantic | disabled
    graphEnabled: bool
    memoryEnabled: bool
    esEnabled: bool                 # ES 混合检索；False = pgvector 回退
    convSummaryEnabled: bool
    ttsAvailable: bool              # 腾讯 TTS 密钥是否已配置
    webProviders: list[str]         # 可用联网搜索服务（仅国内 BoCha，未配置 key 则为空）


@router.get("/settings", response_model=SettingsOut)
async def get_settings(user: User = Depends(get_current_user)):
    stored = user.model_prefs or {}
    merged = {**DEFAULT_MODEL_PREFS, **stored}
    return SettingsOut(
        preferredModel=user.preferred_model,
        ttsEnabled=bool(user.tts_enabled),
        modelPrefs=merged,
        chatVision=vision_llm_available(),
    )


@router.get("/settings/system", response_model=SystemStatusOut)
async def get_system_status(_: User = Depends(get_current_user)):
    """后端运行配置概览：前端状态面板据此渲染，避免写死值与后端实际配置脱节。

    联网搜索服务只报「是否配置了密钥」；境外服务（Tavily/DDG）已移除，
    未配置 BoCha key 时 webProviders 为空，前端据此提示联网搜索不可用。
    """
    providers: list[str] = []
    if settings.BOCHA_API_KEY:
        providers.append("bocha")
    return SystemStatusOut(
        defaultModel=settings.LLM_MODEL,
        embeddingModel=settings.EMBEDDING_MODEL,
        embeddingDim=settings.EMBEDDING_DIM,
        reranker=settings.RERANKER_METHOD if settings.RERANKER_ENABLED else "disabled",
        graphEnabled=settings.GRAPH_ENABLED,
        memoryEnabled=settings.MEMORY_ENABLED,
        esEnabled=settings.ES_ENABLED,
        convSummaryEnabled=settings.CONV_SUMMARY_ENABLED,
        ttsAvailable=bool(settings.TENCENT_TTS_SECRET_ID and settings.TENCENT_TTS_SECRET_KEY),
        webProviders=providers,
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
        chatVision=vision_llm_available(),
    )
