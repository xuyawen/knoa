"""腾讯云 TTS（语音合成）客户端 — 手写 TC3-HMAC-SHA256 签名，不引第三方 SDK。

ponytail: venv 装不了 tencentcloud-sdk-python，复用 stdlib hmac/hashlib/time
+ 已装好的 httpx 直连 tts.tencentcloudapi.com。长文本按字数分块，逐块合成后
拼接（mp3 帧级可追加，安全）。密钥缺失时 text_to_voice 抛 TTSNotConfigured，
由路由层转成 503，前端据此隐藏朗读按钮。
"""
import base64
import hashlib
import hmac
import json
import time
import uuid

import httpx

from app.config import settings


class TTSNotConfigured(Exception):
    """TTS 密钥未配置，前端应据此隐藏朗读按钮。"""


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _sign(
    secret_id: str,
    secret_key: str,
    service: str,
    host: str,
    action: str,
    version: str,
    region: str,
    payload: str,
    timestamp: int,
) -> str:
    # 1. 规范请求（CanonicalRequest）
    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{host}\n"
    signed_headers = "content-type;host"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = "\n".join(
        ["POST", "/", "", canonical_headers, signed_headers, hashed_payload]
    )
    # 2. 待签字符串（StringToSign）
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
    credential_scope = f"{date}/{service}/tc3_request"
    string_to_sign = "\n".join(
        [
            "TC3-HMAC-SHA256",
            str(timestamp),
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    # 3. 签名（派生签名密钥）
    secret_date = _hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _hmac_sha256(secret_date, service)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(
        secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    # 4. 授权头（Authorization）
    return (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


def _split_text(text: str, max_cjk: int = 150) -> list[str]:
    """按字数预算分块：CJK 计 1，其他计 0.5，达到预算即切（腾讯限制 150 汉字/块）。"""
    chunks: list[str] = []
    buf = ""
    budget = 0.0
    for ch in text:
        buf += ch
        budget += 1.0 if ord(ch) > 0x2E80 else 0.5
        if budget >= max_cjk:
            chunks.append(buf)
            buf = ""
            budget = 0.0
    if buf:
        chunks.append(buf)
    return chunks


async def text_to_voice(text: str, voice_type: int | None = None) -> bytes:
    """合成语音，返回原始音频字节（mp3）。密钥缺失抛 TTSNotConfigured。

    Args:
        text: 待合成文本（自动按 150 汉字分块）
        voice_type: 音色，缺省用 settings.TTS_VOICE_TYPE
    """
    if not settings.TENCENT_TTS_SECRET_ID or not settings.TENCENT_TTS_SECRET_KEY:
        raise TTSNotConfigured("TTS 未配置（缺少 TENCENT_TTS_SECRET_ID/SECRET_KEY）")
    voice_type = voice_type or settings.TTS_VOICE_TYPE
    service = "tts"
    host = "tts.tencentcloudapi.com"
    action = "TextToVoice"
    version = "2019-08-23"
    region = settings.TENCENT_TTS_REGION

    text = (text or "").strip()
    if not text:
        raise ValueError("文本为空，无法合成语音")
    chunks = _split_text(text)

    audio_parts: list[bytes] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for piece in chunks:
            payload = json.dumps(
                {
                    "Text": piece,
                    "SessionId": uuid.uuid4().hex,
                    "VoiceType": voice_type,
                    "Codec": settings.TTS_CODEC,
                    "SampleRate": settings.TTS_SAMPLE_RATE,
                    "PrimaryLanguage": 1,  # 中文
                },
                ensure_ascii=False,
            )
            timestamp = int(time.time())
            authorization = _sign(
                settings.TENCENT_TTS_SECRET_ID,
                settings.TENCENT_TTS_SECRET_KEY,
                service,
                host,
                action,
                version,
                region,
                payload,
                timestamp,
            )
            headers = {
                "Authorization": authorization,
                "Content-Type": "application/json; charset=utf-8",
                "Host": host,
                "X-TC-Action": action,
                "X-TC-Version": version,
                "X-TC-Region": region,
                "X-TC-Timestamp": str(timestamp),
            }
            resp = await client.post(
                f"https://{host}", content=payload.encode("utf-8"), headers=headers
            )
            data = resp.json().get("Response", {})
            if "Error" in data:
                raise RuntimeError(
                    f"TTS 合成失败：{data['Error'].get('Code')} {data['Error'].get('Message')}"
                )
            audio_b64 = data.get("Audio")
            if not audio_b64:
                raise RuntimeError("TTS 返回为空")
            audio_parts.append(base64.b64decode(audio_b64))
    return b"".join(audio_parts)
