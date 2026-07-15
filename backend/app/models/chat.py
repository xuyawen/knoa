from typing import Literal

from pydantic import Field, model_validator

from app.models.knowledge import CamelModel


class ChatFile(CamelModel):
    """多模态输入文件（一期仅 image；audio/video 由 MODEL_CAPABILITIES 开关控制）。

    data_b64 为纯 base64（不含 `data:<mime>;base64,` 前缀），
    后端拼回 data URI 后塞进 OpenAI 多模态 content blocks。
    """

    kind: Literal["image", "audio", "video"]
    mime_type: str
    data_b64: str
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
        return self


class SessionCreateIn(CamelModel):
    title: str | None = None


class SessionOut(CamelModel):
    id: str
    title: str
    updated_at: str
    msg_count: int


class SessionMessageOut(CamelModel):
    role: str
    content: str
    citations: list[int] | None = None
    sources: list | None = None
    attachments: list[dict] | None = None


class SessionDetailOut(CamelModel):
    id: str
    title: str
    messages: list[SessionMessageOut]
