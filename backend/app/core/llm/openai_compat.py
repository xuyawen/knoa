from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import logging

from openai import AsyncOpenAI

from app.core.llm.base import LLMConfig, ToolCallResult

logger = logging.getLogger("knoa.llm")

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
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        top_p: float | None = None,
    ) -> AsyncIterator[str]:
        """兼容多提供商流式输出，安全地提取 content + reasoning_content。

        model 覆盖参数：用户偏好模型（settings.preferred_model）透传时生效，
        为空则回落实例默认模型（config.LLM_MODEL）。
        """
        try:
            params: dict[str, Any] = {
                "model": model or self.model,
                "messages": messages,
                "temperature": temperature or self.default_temperature,
                "max_tokens": max_tokens or self.max_tokens,
                "stream": True,
            }
            if top_p is not None:
                params["top_p"] = top_p
            params["messages"] = self._normalize_messages(messages)
            stream = await self.client.chat.completions.create(**params)
        except Exception as e:
            self._diag_messages("stream_chat", messages)
            raise ValueError(f"LLM API 请求失败: {e}")

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # ── 标准字段 content (OpenAI / DeepSeek / DashScope 都有) ──
            content = getattr(delta, "content", "") or ""

            # ponytail: reasoning_content（Agnes 推理模型）按约定丢弃，只透出 content；
            # 否则会把模型思考过程整段泄漏给用户（回答又臭又长）。
            if content:
                yield content

    async def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        model: str | None = None,
        top_p: float | None = None,
    ) -> str:
        """非流式调用"""
        params: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature or self.default_temperature,
            "max_tokens": self.max_tokens,
        }
        if top_p is not None:
            params["top_p"] = top_p
        params["messages"] = self._normalize_messages(messages)
        try:
            response = await self.client.chat.completions.create(**params)
        except Exception as e:
            self._diag_messages("chat", messages)
            raise ValueError(f"LLM API 请求失败: {e}")
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
        """结构化决策 — 用"提示词约束 JSON 输出"替代原生 function calling。

        原因：Agnes 推理模型的 OpenAI 兼容端点对 tools 支持有缺陷，
        传 tools 会回占位函数名 example_function_name，导致决策失败。
        改为让模型只输出一个 JSON 决策对象，本地解析，跨 Provider 稳定。

        Args:
            messages: 对话历史（含 system prompt）
            tools: OpenAI tool schema 列表（仅用于构造"可用动作"说明）
            temperature: 覆盖默认温度（agent 决策建议偏低，0.1~0.3）

        Returns:
            ToolCallResult: name / arguments(解析后dict) / raw_text(思考文字)
        """
        decision = self._build_decision_prompt(tools)
        augmented = list(messages)
        if augmented and augmented[0].get("role") == "system":
            augmented[0] = {
                "role": "system",
                "content": augmented[0]["content"] + "\n\n" + decision,
            }
        else:
            augmented.insert(0, {"role": "system", "content": decision})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self._normalize_messages(augmented),
                temperature=temperature or 0.2,  # agent 决策用更低温度，更确定
                max_tokens=self.max_tokens,
            )
        except Exception as e:
            self._diag_messages("tool_call", augmented)
            raise ValueError(f"LLM API 请求失败: {e}")
        msg = response.choices[0].message
        content = (getattr(msg, "content", "") or "").strip()

        # 抓取 reasoning（如有），用于前端展示思考过程
        raw_text = ""
        try:
            extra = getattr(msg, "__pydantic_extra__", {}) or {}
            raw_text = extra.get("reasoning_content", "") or ""
        except AttributeError:
            pass
        if not raw_text:
            raw_text = content  # 兜底：用 JSON 文本当思考

        parsed = self._extract_json(content)
        name = parsed.get("action") or parsed.get("name") or "direct_answer"
        args = {k: v for k, v in parsed.items() if k not in ("action", "name")}
        return ToolCallResult(name=name, arguments=args, raw_text=raw_text)

    @staticmethod
    def _normalize_messages(messages: list) -> list:
        """防御：把误写成 tuple 的 content 归一化为 str。

        手误（如拼接末尾多一个逗号）会让 `("text",)` 成为单元素 tuple，
        而非字符串。上游会把 content 当列表遍历，对 str 元素调 .get() 报
        'str' object has no attribute 'get'。这里在发送前兜底修复。
        """
        cleaned = []
        for m in messages:
            if not isinstance(m, dict):
                continue
            c = m.get("content")
            if isinstance(c, tuple):
                c = c[0] if len(c) == 1 else "".join(x for x in c if isinstance(x, str))
            cleaned.append({**m, "content": c})
        return cleaned

    @staticmethod
    def _diag_messages(caller: str, messages: list) -> None:
        """出错时打印 messages 结构，定位 'str' object has no attribute 'get' 等。"""
        diag = []
        for i, m in enumerate(messages):
            if isinstance(m, dict):
                c = m.get("content")
                entry = {"i": i, "role": m.get("role"), "ctype": type(c).__name__}
                if isinstance(c, list):
                    entry["elems"] = [type(x).__name__ for x in c]
                    entry["has_str_elem"] = any(not isinstance(x, dict) for x in c)
                if isinstance(c, (tuple, list)):
                    entry["content_repr"] = repr(c)[:400]
                diag.append(entry)
            else:
                diag.append({"i": i, "not_dict": type(m).__name__, "value": repr(m)[:120]})
        logger.warning("[diag:%s] messages=%s", caller, diag)

    @staticmethod
    def _build_decision_prompt(tools: list[dict]) -> str:
        """把 OpenAI tools schema 转成一段"强制 JSON 输出"指令。"""
        lines = [
            "你的一次性决策必须且只能以一个 JSON 对象输出，不要包含任何解释性"
            "文字，不要使用 markdown 代码块。",
            "可用的动作（action）及参数：",
        ]
        for t in tools:
            fn = t.get("function", t)
            name = fn.get("name", "")
            desc = fn.get("description", "")
            props = fn.get("parameters", {}).get("properties", {})
            req = fn.get("parameters", {}).get("required", [])
            param_parts = []
            for p, spec in props.items():
                param_parts.append(f"{p}({spec.get('type', '')}: {spec.get('description', '')})")
            param_desc = "；".join(param_parts) if param_parts else "无"
            lines.append(f'- action="{name}"：{desc} | 参数 {param_desc} | 必填 {req}')
        lines.append('输出 JSON 示例：{"action": "retrieve", "query": "...", "reason": "..."}')
        lines.append('若直接回答：{"action": "direct_answer", "content": "你的回复内容"}')
        return "\n".join(lines)

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从模型输出里稳健地抽出 JSON 对象（兼容 ```json 围栏 / 前后缀噪声）。"""
        import re

        text = (text or "").strip()
        if not text:
            return {}
        # 去掉 ```json ... ``` 围栏
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if m:
                text = m.group(1).strip()
        # 直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 截取第一个 { 到最后一个 }
        s = text.find("{")
        e = text.rfind("}")
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                pass
        return {}
