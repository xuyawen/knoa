"""OSS 前端直传签名端点。

前端上传文件到 OSS 前，先调本端点拿 PostObject 签名，避免 AccessKey 落到浏览器。
签名有效期短（默认 600s），且仅允许写到指定 prefix 下，防越权写。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.core.oss import build_sign
from app.core.security import get_current_user
from app.db import User

router = APIRouter(prefix="/oss", tags=["oss"])


class OssSignIn(BaseModel):
    prefix: str = settings.OSS_UPLOAD_PREFIX   # 子目录前缀，如 uploads/docs
    filename: str                              # 原始文件名（用于拼 key 防重名）
    expire_seconds: int = 600                  # 签名有效期


@router.post("/sign", summary="获取 OSS PostObject 直传签名")
async def oss_sign(
    payload: OssSignIn,
    user: User = Depends(get_current_user),
):
    if not settings.OSS_ENABLED:
        raise HTTPException(status_code=503, detail="OSS 未启用（OSS_ENABLED=False）")
    # 约定前缀必须以全局前缀开头，避免前端自定义写到桶根或其他业务目录
    if not payload.prefix.startswith(settings.OSS_UPLOAD_PREFIX):
        raise HTTPException(status_code=400, detail=f"prefix 必须以 {settings.OSS_UPLOAD_PREFIX} 开头")
    try:
        sign = build_sign(payload.prefix, payload.filename, payload.expire_seconds)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {
        "accessKeyId": sign.access_key_id,
        "policy": sign.policy,
        "signature": sign.signature,
        "host": sign.host,
        "key": sign.key,
        "url": sign.url,
        "expiresAt": sign.expires_at,
    }
