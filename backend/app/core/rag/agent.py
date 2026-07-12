"""Agentic RAG — 由大模型自主决策的智能检索-生成闭环。

核心思路：
  传统 RAG：用户问题 → 固定检索 → 拼接 prompt → 生成（死板）
  Agentic RAG：
    1. LLM 先判断问题类型（打招呼/简单/复杂）
    2. 根据类型决定策略：
       - 打招呼/闲聊 → 直接回答，不检索
       - 简单事实 → 检索一次，够用就答
       - 复杂多步 → 检索 → LLM 评估结果是否足够 → 不够则补充检索 → 再评估...（最多3轮）
    3. 最终基于充分的信息流式生成回答

工具定义（OpenAI function calling schema，仅作为"可用动作"说明传给 LLM 做 JSON 决策）：
  - retrieve：首次检索知识库
  - supplement_search：补充检索（用精炼后的查询词）
  - direct_answer：不检索，直接回答（LLM 在 JSON 里用 action 字段表达）

性能优化：
  - 快速预分类：天气/时间/实时数据/纯数学等明显超出知识库范围的提问，
    直接走 direct_answer，跳过昂贵的 LLM tool_call 决策（省 15~40s/次）。
  - 心跳 ping：在每次 LLM 调用前推送 ping 事件，防止前端因长时间无数据而超时。

对外接口：
  async for event in agent.stream(question, kb_id, session_id):
      # event = {"event": "thinking"|"sources"|"delta"|"done"|"error"|"ping", "data": ...}
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.base import ToolCallResult
from app.core.rag.retriever import HybridRetriever
from app.core.store.redis_store import RedisStore
from app.db import ChatMessage, ChatSession
from app.models.knowledge import SourceItemOut

try:
    from langsmith import traceable
except ImportError:

    def traceable(**kwargs):
        def decorator(fn):
            return fn
        return decorator


# ---------------------------------------------------------------------------
# Tool Schemas (OpenAI function calling format)
# ---------------------------------------------------------------------------

TOOLS_SCHEMA: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "retrieve",
            "description": (
                "从知识库中检索与用户问题相关的文档片段。"
                "使用向量语义检索+BM25关键词检索混合搜索。"
                "当问题涉及具体业务知识、运营策略、合规要求时应调用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用于检索的查询词，可以是原始问题或提炼后的关键词",
                    },
                    "reason": {
                        "type": "string",
                        "description": "为什么需要检索这个问题（简短说明）",
                    },
                },
                "required": ["query", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "supplement_search",
            "description": (
                "当首次检索结果不够充分时，用更精确的查询词进行补充检索。"
                "适用于：首次结果相关性低、覆盖面不够、需要不同角度信息的情况。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "refined_query": {
                        "type": "string",
                        "description": "精炼后的检索词，应比首次查询更聚焦或换一个角度",
                    },
                    "gap_description": {
                        "type": "string",
                        "description": "当前缺失了什么信息，为什么要换个方式搜",
                    },
                },
                "required": ["refined_query", "gap_description"],
            },
        },
    },
]

# System prompt for agent routing
AGENT_SYSTEM_PROMPT = """你是「知海 Knoa」的智能问答路由器。你的任务是分析用户问题并决定最佳处理策略。

## 可选动作
1. **直接回答 (direct_answer)** — 不调用任何工具，直接回复。
   适用场景：打招呼/闲聊（你好、hi、在吗、谢谢等）、常识性问题、纯寒暄。
   也适用于：天气查询、实时股价、时间/日期、体育比分等知识库无法覆盖的实时信息。

2. **调用 retrieve 工具** — 从知识库检索相关文档后回答。
   适用场景：涉及业务知识、运营策略、平台规则、选品方法等问题。

3. **调用 supplement_search 工具** — 当已有检索结果不够充分时，用更精准的关键词再次检索。
   适用场景：首次结果相关性低、信息覆盖不全、需要从其他角度查找。

## 判断原则
- 问题越具体/专业，越应该走检索路径
- 如果问题包含多个子问题或需要对比分析，优先做一次全面检索
- 只有在确实缺少关键信息时才触发补充检索（控制成本）
- 天气、实时数据、时间日期类问题直接回答（知识库无此信息），不要浪费检索
- 回答必须简洁务实，不要自我介绍或罗列功能

## 输出格式
根据判断选择一个动作执行。如果是直接回答，就在 content 里写回复内容；
如果需要检索，就调用对应的工具并填好参数。"""


# ---------------------------------------------------------------------------
# 快速预分类：明显不需要检索的问题，跳过昂贵的 LLM tool_call（省 15~40s）
# ---------------------------------------------------------------------------

_SKIP_RETRIEVAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"(今天|明天|后天|本周|下周|这周|那周).*?(天气|气温|温度|下雨|下雪|晴|阴|多云|台风|暴雨|雾霾)", re.I),
    re.compile(r"(天气|气温|温度).*(怎么|怎么样|如何|多少度|几度|会.*吗|呢？?$)", re.I),
    re.compile(r"现在(几点|什么时间|几号|星期几|农历)", re.I),
    re.compile(r"^(现在)?(几点了?|什么时间|今天星期|今天几号)", re.I),
    re.compile(r"(股票|基金|汇率|金价|油价|比特币|BTC|ETH).*(涨|跌|行情|价格|多少|走势)", re.I),
    re.compile(r"^\d+[\+\-\*\/]\d+", re.I),  # 纯数学计算
    re.compile(r"^(翻译|translate)\s*", re.I),  # 翻译请求
]


def _should_skip_retrieval(question: str) -> bool:
    """快速判断是否应该跳过 RAG 检索（纯启发式，不调 LLM）。"""
    q = question.strip()
    return any(p.search(q) for p in _SKIP_RETRIEVAL_PATTERNS)


class AgenticRAGAgent:
    """Agentic RAG 代理 — 用 LLM 驱动的决策闭环替代固定检索流程。

    与传统 pipeline 的区别：
    - 不是"有问必检"，而是由模型判断该不该检
    - 不是"检完就用"，而是先评估质量再决定要不要补检
    - 支持多步迭代（默认最多3轮），复杂问题可以逐步收敛
    """

    MAX_STEPS = 3  # 最大检索轮数（防止无限循环和成本失控）

    def __init__(
        self,
        retriever: HybridRetriever,
        llm,  # LLMProvider protocol（需支持 tool_call）
        redis: RedisStore,
        db: AsyncSession,
    ):
        self.retriever = retriever
        self.llm = llm
        self.redis = redis
        self.db = db

    @traceable(name="agentic_rag_stream", tags=["agent", "rag"])
    async def stream_answer(
        self,
        question: str,
        kb_id: str | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[dict]:
        """主入口：返回 SSE 兼容的事件流。

        Yielded events:
          {"event": "thinking", "data": {"step": N, "action": "...", "detail": "..."}}
          {"event": "sources",  "data": [...]}  # SourceItemOut dicts
          {"event": "delta",    "data": {"content": "..."}}
          {"event": "done",     "data": {"messageId": ..., "citations": ..., "sessionId": ...}}
          {"event": "error",    "data": {"message": "..."}}
        """
        try:
            # ---- 会话 & 持久化 ----
            session = await self._get_or_create_session(session_id, question)
            self.db.add(ChatMessage(session_id=session.id, role="user", content=question))
            await self.db.flush()

            # trending 计数
            try:
                await self.redis.incr_trending(question)
            except Exception:
                pass

            # ---- 快速预分类：明显不需要检索的问题直接跳过 LLM 决策 ----
            all_sources: list[dict] = []  # 两条路径共用（持久化需要）
            final_answer_text: str = ""   # 同上

            if _should_skip_retrieval(question):
                yield {
                    "event": "thinking",
                    "data": {
                        "step": 0,
                        "action": "direct_answer",
                        "detail": "识别为常识/实时问题，跳过检索直接回答",
                        "raw_reasoning": "",
                    },
                }
                # 用一次轻量 LLM 调用生成回复（不经过 agent 决策）
                quick_messages = [
                    {"role": "system", "content": (
                        "你是「知海 Knoa」，一个跨境电商运营知识助手。"
                        "用户问了一个知识库无法覆盖的常识/实时类问题（如天气、时间、股价等），"
                        "请友好简洁地回答。如果确实不知道，就直说。不要自我介绍或罗列功能。"
                    )},
                    {"role": "user", "content": question},
                ]
                full_answer = ""
                async for delta in self.llm.stream_chat(quick_messages):
                    full_answer += delta
                    yield {"event": "delta", "data": {"content": delta}}
                final_answer_text = full_answer
            else:
                # ---- Agent Loop ----
                messages = [
                    {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                ]
                step = 0

                while step < self.MAX_STEPS:
                    step += 1

                    # 心跳 ping：在每次 LLM 调用前通知前端"我还在干活"
                    yield {"event": "ping", "data": {"ts": time.time(), "step": step}}

                    # LLM 决策：调工具 or 直接回答
                    result: ToolCallResult = await self.llm.tool_call(
                        messages, tools=TOOLS_SCHEMA, temperature=0.2
                    )

                    # 动作名归一化（prompt 决策可能因模型输出波动而偏离预设值）
                    name = result.name
                    if name not in ("retrieve", "supplement_search", "direct_answer"):
                        if "query" in result.arguments:
                            name = "retrieve"
                        elif "refined_query" in result.arguments:
                            name = "supplement_search"
                        elif "content" in result.arguments:
                            name = "direct_answer"
                        else:
                            name = "direct_answer"
                        result = ToolCallResult(
                            name=name,
                            arguments=result.arguments,
                            raw_text=result.raw_text,
                        )

                    # 推送 thinking 事件（前端可展示决策过程）
                    action_desc = self._describe_action(result)
                    yield {
                        "event": "thinking",
                        "data": {
                            "step": step,
                            "action": result.name,
                            "detail": action_desc,
                            "raw_reasoning": result.raw_text[:500] if result.raw_text else "",
                        },
                    }

                    if result.name == "direct_answer":
                        # LLM 认为不需要检索，直接回答
                        final_answer_text = result.arguments.get("content", "")
                        break

                    elif result.name == "retrieve":
                        query = result.arguments.get("query", question)
                        retrieved = await self.retriever.retrieve(query, kb_id, top_k=5)

                        if retrieved:
                            sources = self._format_sources(retrieved)
                            all_sources.extend(sources)
                            yield {"event": "sources", "data": sources}

                            # 把检索结果注入上下文，让 LLM 决定下一步
                            context_text = self._sources_to_context(retrieved)
                            messages.append({
                                "role": "assistant",
                                "content": f"[已调用检索 retrieve，针对「{query}」检索到 {len(retrieved)} 条相关文档]",
                            })
                            messages.append({
                                "role": "user",
                                "content": (
                                    f"检索结果：\n{context_text}\n\n"
                                    "请判断：\n"
                                    "1. 这些信息足以回答用户的原问题吗？\n"
                                    "2. 如果足够，请直接给出最终回答（action=direct_answer，content=回复内容）。\n"
                                    "3. 如果不足，请调用 supplement_search 补充检索"
                                    "（action=supplement_search，refined_query=更聚焦的查询词，gap_description=缺失的信息）。"
                                ),
                            })
                            continue  # 进入下一轮决策
                        else:
                            # 检索无结果
                            messages.append({
                                "role": "assistant",
                                "content": "[已调用 retrieve 工具，但未找到相关文档]",
                            })
                            messages.append({
                                "role": "user",
                                "content": (
                                    "检索未找到相关结果。请判断：\n"
                                    "- 如果你可以基于通用知识回答，请直接回复。\n"
                                    "- 如果你认为知识库中可能有相关信息但没搜到，可以尝试 supplement_search 换个关键词。"
                                ),
                            })
                            continue

                    elif result.name == "supplement_search":
                        refined_query = result.arguments.get("refined_query", question)
                        gap = result.arguments.get("gap_description", "")
                        retrieved = await self.retriever.retrieve(refined_query, kb_id, top_k=5)

                        if retrieved:
                            sources = self._format_sources(retrieved)
                            all_sources.extend(sources)
                            yield {"event": "sources", "data": sources}

                            context_text = self._sources_to_context(retrieved)
                            messages.append({
                                "role": "assistant",
                                "content": f"[已调用补充检索 supplement_search，针对「{gap}」检索到 {len(retrieved)} 条]",
                            })
                            messages.append({
                                "role": "user",
                                "content": (
                                    f"补充检索结果：\n{context_text}\n\n"
                                    "结合之前所有信息，请判断：\n"
                                    "1. 现在信息是否足够回答用户问题？\n"
                                    "2. 足够就 action=direct_answer 直接给最终回答；"
                                    "不足可以再补充一次（最多3轮）。"
                                ),
                            })
                            continue
                        else:
                            messages.append({
                                "role": "assistant",
                                "content": "[补充检索也未找到新结果]",
                            })
                            messages.append({
                                "role": "user",
                                "content": "补充检索也没结果。请基于已有信息尽量回答，或告知用户知识库暂无相关信息。",
                            })
                            continue

                    else:
                        # 未知的工具名（兜底）
                        final_answer_text = f"抱歉，系统遇到了未知状态 ({result.name})。请重试。"
                        break

                # ---- 流式生成最终答案（仅 Agent 路径需要） ----
                    if not final_answer_text:
                        # 构建最终 prompt（含所有累积的上下文）
                        final_messages = self._build_final_prompt(
                            question, all_sources, messages
                        )
                        full_answer = ""
                        async for delta in self.llm.stream_chat(final_messages):
                            full_answer += delta
                            yield {"event": "delta", "data": {"content": delta}}
                        final_answer_text = full_answer
                    else:
                        # direct_answer 路径：把文本拆成单个 delta 以保持前端兼容
                        yield {"event": "delta", "data": {"content": final_answer_text}}

            # ---- 持久化 + done 事件（两条路径共用） ----
            citations = self._extract_citations(final_answer_text)
            assistant_msg = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=final_answer_text,
                citations=citations,
                sources=all_sources,
            )
            self.db.add(assistant_msg)
            await self.db.commit()

            yield {
                "event": "done",
                "data": {
                    "messageId": str(assistant_msg.id),
                    "citations": citations,
                    "sessionId": str(session.id),
                },
            }

        except Exception as e:
            yield {"event": "error", "data": {"message": str(e)}}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _describe_action(self, result: ToolCallResult) -> str:
        if result.name == "direct_answer":
            return "判断为无需检索，直接回答"
        if result.name == "retrieve":
            q = result.arguments.get("query", "")[:60]
            reason = result.arguments.get("reason", "")[:40]
            return f"检索知识库：「{q}...」（{reason}）"
        if result.name == "supplement_search":
            q = result.arguments.get("refined_query", "")[:60]
            gap = result.arguments.get("gap_description", "")[:40]
            return f"补充检索：「{q}...」（{gap}）"
        return f"执行 {result.name}"

    def _format_sources(self, retrieved: list[dict]) -> list[dict]:
        return [
            SourceItemOut(
                id=r["id"], kb=r["kb"], title=r["title"],
                snippet=r["snippet"], confidence=r["confidence"],
            ).model_dump(by_alias=True)
            for r in retrieved
        ]

    def _sources_to_context(self, retrieved: list[dict]) -> str:
        parts = []
        for r in retrieved:
            parts.append(f"\n[{r['id']}] {r['title']} ({r['kb']})\n{r['content']}")
        return "\n".join(parts)

    def _build_final_prompt(
        self,
        question: str,
        all_sources: list[dict],
        conversation_messages: list[dict],
    ) -> list[dict]:
        """构建最终流式生成的 prompt，含完整检索上下文。"""
        context = ""
        for s in all_sources:
            context += f"\n[{s['id']}] {s['title']}\n{s.get('snippet', '')}\n"

        system = (
            "你是「知海 Knoa」，一个跨境电商运营知识助手。\n"
            "请基于以下检索到的知识库内容回答用户问题，回答必须忠实于来源内容。\n\n"
            "引用规则：\n"
            "- 引用时使用 [1] [2] 这样的标注，数字对应来源编号\n"
            "- 如果知识库内容不足以回答，明确告知用户\n\n"
            f"知识库来源：\n{context}"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]

    def _extract_citations(self, text: str) -> list[int]:
        import re
        matches = re.findall(r"\[(\d+)\]", text)
        return sorted(set(int(m) for m in matches))

    async def _get_or_create_session(self, session_id: str | None, question: str) -> ChatSession:
        if session_id:
            result = await self.db.execute(
                select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
            )
            session = result.scalar_one_or_none()
            if session:
                return session
        session = ChatSession(title=question[:50])
        self.db.add(session)
        await self.db.flush()
        return session
