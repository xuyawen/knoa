"""语音播报端点：把文本合成为语音返回前端播放。"""
import base64
import httpx

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_user
from app.core.tts import TTSNotConfigured, text_to_voice
from app.db import User

router = APIRouter()


class TTSRequest(BaseModel):
    text: str
    voiceType: int | None = None


class TTSOut(BaseModel):
    audio: str            # base64 编码的 mp3
    contentType: str = "audio/mpeg"


@router.post("/tts", response_model=TTSOut)
async def tts(req: TTSRequest, _: User = Depends(get_current_user)):  # noqa: B008  (FastAPI 鉴权依赖惯用法)
    """合成语音：密钥未配置返回 503（前端据此隐藏朗读按钮）。"""
    try:
        audio = await text_to_voice(req.text, req.voiceType)
    except TTSNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (RuntimeError, httpx.HTTPError) as e:
        raise HTTPException(status_code=502, detail=f"TTS 合成失败：{e}") from e
    return TTSOut(audio=base64.b64encode(audio).decode("ascii"))
