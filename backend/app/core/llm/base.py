from typing import AsyncIterator, Protocol

from pydantic import BaseModel


class LLMConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.3
    max_tokens: int = 2000


class LLMProvider(Protocol):
    async def stream_chat(
        self, messages: list[dict[str, str]], temperature: float | None = None
    ) -> AsyncIterator[str]: ...

    async def chat(
        self, messages: list[dict[str, str]], temperature: float | None = None
    ) -> str: ...
