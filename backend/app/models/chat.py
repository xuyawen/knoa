from pydantic import Field

from app.models.knowledge import CamelModel


class AskRequest(CamelModel):
    question: str = Field(..., min_length=1, max_length=2000)
    knowledge_base: str | None = None
    session_id: str | None = None


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


class SessionDetailOut(CamelModel):
    id: str
    title: str
    messages: list[SessionMessageOut]
