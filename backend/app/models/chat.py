from typing import Literal

from pydantic import Field, model_validator

from app.models.knowledge import CamelModel

# 多模态附件上限（与 P1-4 上传 20MB 对齐）：
# base64 约为原始字节的 4/3，20MB 原始 ≈ 28MB base64 字符串。
MAX_FILE_B64_LEN = 28_000_000
MAX_FILES_PER_ASK = 5


class ChatFile(CamelModel):
    """多模态输入文件（一期仅 image；audio/video 由 MODEL_CAPABILITIES 开关控制）。

    data_b64 为纯 base64（不含 `data:<mime>;base64,` 前缀），
    后端拼回 data URI 后塞进 OpenAI 多模态 content blocks。
    """

    kind: Literal["image", "audio", "video"]
    mime_type: str
    data_b64: str = Field(..., max_length=MAX_FILE_B64_LEN)
    name: str | None = None


class AskRequest(CamelModel):
    question: str = Field(default="", max_length=2000)
    knowledge_base: str | None = None
    session_id: str | None = None
    files: list[ChatFile] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_non_empty(self) -> "AskRequest":
        if not self.question.strip() and not self.files:
            raise ValueError("请输入问题或上传图片")
        if len(self.files) > MAX_FILES_PER_ASK:
            raise ValueError(f"单次最多上传 {MAX_FILES_PER_ASK} 个附件")
        return self


class SessionCreateIn(CamelModel):
    title: str | None = None


class SessionOut(CamelModel):
    id: str
    title: str
    updated_at: str
    msg_count: int
    summary: str | None = None


class SessionMessageOut(CamelModel):
    role: str
    content: str
    citations: list[int] | None = None
    sources: list | None = None
    attachments: list[dict] | None = None


class SessionDetailOut(CamelModel):
    id: str
    title: str
    summary: str | None = None
    messages: list[SessionMessageOut]
