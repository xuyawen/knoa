from typing import AsyncIterator, Protocol

from pydantic import BaseModel


class LLMConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.3
    max_tokens: int = 2000


class ToolCallResult(BaseModel):
    """LLM 单次 tool-call 的结构化输出"""
    name: str
    arguments: dict  # 解析后的 JSON args
    raw_text: str = ""  # LLM 原始 reasoning/思考文字（如有）


class LLMProvider(Protocol):
    async def stream_chat(
        self, messages: list[dict[str, str]], temperature: float | None = None
    ) -> AsyncIterator[str]: ...

    async def chat(
        self, messages: list[dict[str, str]], temperature: float | None = None
    ) -> str: ...

    async def tool_call(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        temperature: float | None = None,
    ) -> ToolCallResult: ...
