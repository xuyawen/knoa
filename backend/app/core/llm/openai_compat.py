from __future__ import annotations

import json
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.llm.base import LLMConfig, ToolCallResult

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

    @traceable(name="llm_tool_call", tags=["llm", "tool"])
    async def tool_call(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        temperature: float | None = None,
    ) -> ToolCallResult:
        """结构化 function calling — 让 LLM 选择并返回一个工具调用。

        Args:
            messages: 对话历史（含 system prompt）
            tools: OpenAI tool schema 列表
            temperature: 覆盖默认温度（agent 决策建议偏低，0.1~0.3）

        Returns:
            ToolCallResult: name / arguments(解析后dict) / raw_text
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",  # LLM 自主决定是否调工具
            temperature=temperature or 0.2,  # agent 决策用更低温度，更确定
            max_tokens=self.max_tokens,
        )
        choice = response.choices[0]
        msg = choice.message

        # 提取 reasoning_text（如有），用于前端展示"思考过程"
        raw_text = ""
        try:
            extra = getattr(msg, "__pydantic_extra__", {}) or {}
            raw_text = extra.get("reasoning_content", "") or ""
        except AttributeError:
            pass

        # 有工具调用 → 返回结构化结果
        if getattr(msg, "tool_calls", None) and msg.tool_calls:
            tc = msg.tool_calls[0]
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeArgsError:
                args = {"raw": tc.function.arguments or ""}
            return ToolCallResult(
                name=tc.function.name,
                arguments=args,
                raw_text=raw_text,
            )

        # 没有工具调用 → LLM 直接回答（说明问题不需要检索）
        content = (getattr(msg, "content", "") or "").strip()
        return ToolCallResult(
            name="direct_answer",
            arguments={"content": content},
            raw_text=raw_text,
        )
