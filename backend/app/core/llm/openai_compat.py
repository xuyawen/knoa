from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.llm.base import LLMConfig

try:
    from langsmith import traceable
except ImportError:
    # ponytail: langsmith 未安装时 no-op
    def traceable(**kwargs):
        def decorator(fn):
            return fn
        return decorator


class OpenAICompatProvider:
    """OpenAI 兼容客户端, 支持 OpenAI/DeepSeek/Moonshot/通义千问等"""

    def __init__(self, config: LLMConfig):
        self.client = AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)
        self.model = config.model
        self.default_temperature = config.temperature
        self.max_tokens = config.max_tokens

    @traceable(name="llm_stream", tags=["llm"])
    async def stream_chat(
        self, messages: list[dict[str, str]], temperature: float | None = None
    ) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.default_temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def chat(
        self, messages: list[dict[str, str]], temperature: float | None = None
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.default_temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content or ""
