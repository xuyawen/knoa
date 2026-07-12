from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.llm.base import LLMConfig

try:
    from langsmith import traceable
except ImportError:

    def traceable(**kwargs):  # type: ignore[misc]
        def decorator(fn):
            return fn

        return decorator


class OpenAICompatProvider:
    """OpenAI 兼容客户端 — Agnes AI / OpenAI / DeepSeek / DashScope 都能用"""

    def __init__(self, config: LLMConfig):
        self.client = AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)
        self.model = config.model
        self.default_temperature = config.temperature
        self.max_tokens = config.max_tokens

    @traceable(name="llm_stream", tags=["llm"])
    async def stream_chat(
        self, messages: list[dict[str, str]], temperature: float | None = None
    ) -> AsyncIterator[str]:
        """兼容多提供商流式输出，安全地提取 content + reasoning_content"""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.default_temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
        except Exception as e:
            raise ValueError(f"LLM API 请求失败: {e}")

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # ── 标准字段 content (OpenAI / DeepSeek / DashScope 都有) ──
            content = getattr(delta, "content", "") or ""

            # ── reasoning_content (Agnes AI 推理模型塞在这里) ──
            # OpenAI SDK 的 ChoiceDelta 不允许 getattr(x, "reasoning_content", "")
            # 因为它用了 extra="forbid"，多余字段不存进去
            # 所以用 __pydantic_extra__ 取原始 JSON 透传过来的字段
            try:
                extra_fields = delta.__pydantic_extra__ or {}
            except AttributeError:
                extra_fields = {}
            reasoning = extra_fields.get("reasoning_content", "") or ""

            # ponytail: 推理内容只用于服务端调试/可观测，绝不拼进用户可见的回答，
            # 否则会把模型的"思考过程"整段泄漏给用户（表现为回答又臭又长）
            if content:
                yield content

    async def chat(
        self, messages: list[dict[str, str]], temperature: float | None = None
    ) -> str:
        """非流式调用"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.default_temperature,
            max_tokens=self.max_tokens,
        )
        msg = response.choices[0].message
        # 只返回真正的回答 content，丢弃 reasoning_content（推理过程不对外暴露）
        return (getattr(msg, "content", "") or "").strip()
