from pydantic import Field

from app.models.knowledge import CamelModel


class AskRequest(CamelModel):
    question: str = Field(..., min_length=1, max_length=2000)
    knowledge_base: str | None = None
    session_id: str | None = None
