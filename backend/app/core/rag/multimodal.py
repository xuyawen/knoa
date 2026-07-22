"""多模态解析器（Phase 7 多模态扩展）。

把音频 / 视频 / 图片等非文本文件转成「可检索文本」，统一进 DocChunk
（与 md/txt/docx/pdf 的纯文本走同一条摄入链路）。

沙箱约束（venv 装不了第三方包、且 Agnes 仅确认支持 image）：
- 图片：直接调多模态 LLM（Agnes image 能力）做视觉描述 + OCR，最稳、零额外依赖。
- 音频：优先走 OpenAI 兼容的 audio.transcriptions（需 STT 服务 + key），
  无服务/失败时软降级为占位说明（不阻塞主流程）。
- 视频：需要 ffmpeg 抽帧 + ASR 转录，沙箱缺失时软降级为占位说明。
所有降级都返回真实 ParseResult（占位文本也可被检索命中），保证上传链路不崩。
"""
from __future__ import annotations

import base64
import io
import logging

from app.config import settings
from app.core.rag.parsers import ParseResult, UnsupportedFormatError

logger = logging.getLogger(__name__)

IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}
AUDIO_EXTS = {"mp3", "wav", "m4a", "ogg", "flac", "aac"}
VIDEO_EXTS = {"mp4", "mov", "webm", "mkv", "avi"}

_MIME_BY_EXT = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp",
}

VISION_PROMPT = (
    "请仔细观察这张图片，完成两件事：\n"
    "1) 提取图片中所有的可见文字（OCR），逐行输出，保留原始排版；\n"
    "2) 用中文描述图片的核心内容、主体、场景与关键信息。\n"
    "若图片不含任何文字，请直接说明「无可见文字」并给出描述。"
)


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _guess_mime(filename: str) -> str:
    return _MIME_BY_EXT.get(_ext(filename), "image/png")


def is_multimodal_ext(ext: str) -> bool:
    return ext in IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS


async def parse_image(filename: str, data: bytes, llm) -> ParseResult:
    """图片 → 视觉描述 + OCR 文本（走多模态 LLM 的流式通道，规避推理模型 content 为空）。"""
    b64 = base64.b64encode(data).decode("ascii")
    mime = _guess_mime(filename)
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ],
    }]
    parts: list[str] = []
    try:
        async for chunk in llm.stream_chat(messages, temperature=0.2, max_tokens=1200):
            parts.append(chunk)
    except Exception as e:  # 视觉调用失败不阻塞上传，降级占位
        logger.warning("image vision parse failed (fallback placeholder): %s", e)
        return ParseResult(f"[图片 {filename}：视觉描述生成失败，仅记录元信息]", "image")
    text = "".join(parts).strip()
    if not text:
        text = f"[图片 {filename}：未能生成视觉描述]"
    return ParseResult(text, "image")


async def _transcribe(filename: str, data: bytes) -> str | None:
    """OpenAI 兼容音频转录；无 SDK / 无服务 / 失败均返回 None（交由上层降级）。"""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return None
    base_url = settings.LLM_BASE_URL
    api_key = settings.LLM_API_KEY
    if not (base_url and api_key):
        return None
    model = getattr(settings, "STT_MODEL", None) or "whisper-1"
    try:
        client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        res = await client.audio.transcriptions.create(
            model=model, file=(filename, io.BytesIO(data))
        )
        return (getattr(res, "text", None) or "").strip() or None
    except Exception as e:
        logger.warning("STT transcription failed (fallback placeholder): %s", e)
        return None


async def parse_audio(filename: str, data: bytes, llm=None) -> ParseResult:
    """音频 → ASR 转录文本；无 STT 服务时软降级为占位说明。"""
    text = await _transcribe(filename, data)
    if text is None:
        return ParseResult(
            f"[音频 {filename}：当前环境未配置 ASR（语音转写）服务，暂无法转录为可检索文本]",
            "audio",
        )
    return ParseResult(text, "audio")


async def parse_video(filename: str, data: bytes, llm=None) -> ParseResult:
    """视频 → 抽帧(ffmpeg) + 音频 ASR；沙箱缺失时软降级为占位说明。"""
    # 真实环境：用 ffmpeg 抽首帧走 parse_image + 抽音轨走 parse_audio 再拼接。
    # 沙箱无 ffmpeg/STT，这里给出清晰占位，保证上传链路不崩、文件可入库。
    return ParseResult(
        f"[视频 {filename}：当前环境未配置视频解析（需 ffmpeg 抽帧 + ASR 转写），"
        "暂无法提取可检索文本]",
        "video",
    )


async def parse_multimodal(filename: str, data: bytes, llm) -> ParseResult:
    """按扩展名把非文本文件分发到对应多模态解析器。"""
    ext = _ext(filename)
    if ext in IMAGE_EXTS:
        return await parse_image(filename, data, llm)
    if ext in AUDIO_EXTS:
        return await parse_audio(filename, data, llm)
    if ext in VIDEO_EXTS:
        return await parse_video(filename, data, llm)
    raise UnsupportedFormatError(
        f"不支持的文件格式 .{ext or '未知'}，当前支持：md / txt / docx / pdf / 图片 / 音频 / 视频"
    )
