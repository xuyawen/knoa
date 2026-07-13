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

import asyncio
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm.base import ToolCallResult
from app.core.memory import MemoryStore
from app.core.rag.retriever import HybridRetriever
from app.core.rag.web_search import WebSearcher
from app.core.store.redis_store import RedisStore
from app.database import AsyncSessionLocal
from app.db import ChatMessage, ChatSession
from app.models.knowledge import SourceItemOut

logger = logging.getLogger(__name__)

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
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "联网搜索实时/外部信息。当需要查询知识库未覆盖的最新政策、"
                "实时汇率/股价、新闻事件、或任何需要联网才能确认的事实时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用于联网搜索的查询词",
                    },
                    "reason": {
                        "type": "string",
                        "description": "为什么需要联网搜索（简短说明）",
                    },
                },
                "required": ["query", "reason"],
            },
        },
    },
]

# System prompt for agent routing
AGENT_SYSTEM_PROMPT = """你是「知海 Knoa」的智能问答路由器。你的任务是分析用户问题并决定最佳处理策略。

## 可选动作
1. **直接回答 (direct_answer)** — 不调用任何工具，直接回复。
   适用场景：打招呼/闲聊（你好、hi、在吗、谢谢等）、常识性问题、纯寒暄。

2. **调用 retrieve 工具** — 从知识库检索相关文档后回答。
   适用场景：涉及业务知识、运营策略、平台规则、选品方法等问题。

3. **调用 supplement_search 工具** — 当已有检索结果不够充分时，用更精准的关键词再次检索。
   适用场景：首次结果相关性低、信息覆盖不全、需要从其他角度查找。

4. **调用 web_search 工具** — 联网搜索实时/外部信息。
   适用场景：汇率/股价/金价等实时数据、最新政策或平台公告、新闻事件、
   知识库明显过时的内容、或任何需要联网才能确认的事实。

## 判断原则
- 问题越具体/专业，越应该走检索路径
- 如果问题包含多个子问题或需要对比分析，优先做一次全面检索
- 只有在确实缺少关键信息时才触发补充检索（控制成本）
- 天气、时间日期类问题：若无知识库答案，用 web_search 联网查询实时信息，不要凭记忆编造
- 汇率/股价/最新政策/新闻等实时或易变信息：优先 web_search 联网核实
- 知识库能回答的运营/合规问题优先走 retrieve，不要无谓联网
- 回答必须简洁务实，不要自我介绍或罗列功能

## 输出格式
根据判断选择一个动作执行。如果是直接回答，就在 content 里写回复内容；
如果需要检索或联网，就调用对应的工具（retrieve / supplement_search / web_search）并填好参数。"""


# ---------------------------------------------------------------------------
# 快速预分类：明显不需要检索的问题，跳过昂贵的 LLM tool_call（省 15~40s）
# ---------------------------------------------------------------------------

_SKIP_RETRIEVAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"现在(几点|什么时间|几号|星期几|农历)", re.I),
    re.compile(r"^(现在)?(几点了?|什么时间|今天星期|今天几号)", re.I),
    re.compile(r"^[0-9]+[+\-*/][0-9]+", re.I),  # 纯数学计算
    re.compile(r"^(翻译|translate) +", re.I),  # 翻译请求
]

def _should_skip_retrieval(question: str) -> bool:
    """快速判断是否应该跳过 RAG 检索（纯启发式，不调 LLM）。"""
    q = question.strip()
    return any(p.search(q) for p in _SKIP_RETRIEVAL_PATTERNS)


# 需要联网搜索实时/易变信息的快速预分类（避免 LLM 凭记忆编造）
_WEB_SEARCH_PATTERNS: list[re.Pattern] = [
    re.compile(r"(今天|明天|后天|本周|下周|这周|那周).*?(天气|气温|温度|下雨|下雪|晴|阴|多云|台风|暴雨|雾霾)", re.I),
    re.compile(r"(天气|气温|温度).*(怎么|怎么样|如何|多少度|几度|会.*吗|呢？?$)", re.I),
    re.compile(r"(汇率|美金|美元|人民币|人民币兑|兑美元|eur|gbp|jpy).*(多少|走势|换算|现在|今日|今天)", re.I),
    re.compile(r"(美元|人民币|欧元|英镑|日元|加元).*(兑|汇率|换|多少)", re.I),
    re.compile(r"(金价|黄金价格|原油|油价|比特币|btc|eth|股票|股价|纳斯达克|道琼斯).*(多少|报价|行情|现在|今日)", re.I),
    re.compile(r"(最新|新的|近期|2024|2025|今年|本月).*(政策|规定|公告|费率|费用|关税|税)", re.I),
    re.compile(r"(新闻|热点|事件|刚刚|今天).*(发生|发布|宣布|消息)", re.I),
    re.compile(r"(amazon|亚马逊).*(new|update|policy|fee|fba).*(2024|2025|recent|latest)", re.I),
]

def _should_web_search(question: str) -> bool:
    """判断是否需要联网搜索实时/易变信息（避免 LLM 凭记忆编造）。"""
    q = question.strip()
    return any(p.search(q) for p in _WEB_SEARCH_PATTERNS)


class AgenticRAGAgent:
    """Agentic RAG 代理 — 用 LLM 驱动的决策闭环替代固定检索流程。"""

    MAX_STEPS = 3

    def __init__(
        self,
        retriever: HybridRetriever,
        llm,
        redis: RedisStore,
        db: AsyncSession,
        user_id: str | None = None,
        memory: "MemoryStore | None" = None,
    ):
        self.retriever = retriever
        self.llm = llm
        self.redis = redis
        self.db = db
        self.user_id = user_id
        self.memory = memory
        self._memories: list[str] = []  # 本轮召回的该用户长期记忆

    @traceable(name="agentic_rag_stream", tags=["agent", "rag"])
    async def stream_answer(
        self,
        question: str,
        kb_id: str | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[dict]:
        """主入口：返回 SSE 兼容的事件流。"""
        try:
            # ---- 会话 & 持久化 ----
            session = await self._get_or_create_session(session_id, question)
            self.db.add(ChatMessage(session_id=session.id, role="user", content=question))
            await self.db.flush()

            # ponytail: 只统计真实业务提问，过滤打招呼/闲聊/天气等，避免污染"高频问题"
            if not _should_skip_retrieval(question):
                try:
                    await self.redis.incr_trending(question)
                except Exception:
                    pass

            # ── Mem0 长期记忆：召回该用户的相关记忆，注入后续所有 prompt ──
            if self.memory and self.user_id and settings.MEMORY_ENABLED:
                try:
                    self._memories = await self.memory.retrieve(
                        self.user_id, question, self.db, settings.MEMORY_TOP_K
                    )
                except Exception as e:
                    logger.warning("memory retrieve failed (skip inject): %s", e)
                    self._memories = []

            all_sources: list[dict] = []
            final_answer_text: str = ""

            # ── 快速预分类路径 ──
            if _should_skip_retrieval(question):
                yield {
                    "event": "thinking",
                    "data": {"step": 0, "action": "direct_answer",
                             "detail": "识别为常识/实时问题，跳过检索直接回答", "raw_reasoning": ""},
                }
                quick_messages = [
                    {"role": "system", "content": (
                        "你是「知海 Knoa」，一个跨境电商运营知识助手。"
                        "用户问了一个知识库无法覆盖的常识/实时类问题（如天气、时间、股价等），"
                    "请友好简洁地回答。如果确实不知道，就直说。不要自我介绍或罗列功能。"
                        ) + self._memory_section()},
                    {"role": "user", "content": question},
                ]
                full_answer = ""
                async for delta in self.llm.stream_chat(quick_messages):
                    full_answer += delta
                    yield {"event": "delta", "data": {"content": delta}}
                final_answer_text = full_answer

            # 联网搜索快速路径
            elif _should_web_search(question):
                yield {
                    "event": "thinking",
                    "data": {"step": 0, "action": "web_search",
                             "detail": "识别为实时/易变信息，联网搜索", "raw_reasoning": ""},
                }
                searcher = WebSearcher()
                try:
                    web = await searcher.search(question, max_results=5)
                finally:
                    await searcher.aclose()
                if web:
                    # 重新连续编号，接在 all_sources 之后，避免与知识库来源（1..N）撞号
                    for i, w in enumerate(web, len(all_sources) + 1):
                        w["id"] = i
                        w["chunk_id"] = f"web:{i}"
                    all_sources.extend(web)
                    yield {"event": "sources", "data": self._format_sources(web)}
                final_messages = self._build_final_prompt(question, all_sources, None)
                full_answer = ""
                async for delta in self.llm.stream_chat(final_messages):
                    full_answer += delta
                    yield {"event": "delta", "data": {"content": delta}}
                final_answer_text = full_answer

            # Agent Loop 路径
            else:
                messages = [
                    {"role": "system", "content": AGENT_SYSTEM_PROMPT + self._memory_section()},
                    {"role": "user", "content": question},
                ]
                step = 0

                while step < self.MAX_STEPS:
                    step += 1
                    yield {"event": "ping", "data": {"ts": time.time(), "step": step}}

                    result: ToolCallResult = await self.llm.tool_call(
                        messages, tools=TOOLS_SCHEMA, temperature=0.2
                    )

                    # 动作名归一化
                    name = result.name
                    if name == "web_search":
                        pass  # 已是正确动作，跳过归一化
                    elif name not in ("retrieve", "supplement_search", "direct_answer"):
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

                    action_desc = self._describe_action(result)
                    # ponytail: direct_answer 但已有检索结果时，实为「基于检索生成」，
                    # 在前端就标成 generate，避免误导用户以为「没检索就回答」。
                    display_action = result.name
                    display_detail = action_desc
                    if result.name == "direct_answer" and all_sources:
                        display_action = "generate"
                        display_detail = f"检索结果已充足（{len(all_sources)} 条），生成回答"

                    yield {
                        "event": "thinking",
                        "data": {"step": step, "action": display_action,
                                 "detail": display_detail,
                                 "raw_reasoning": (result.raw_text or "")[:500]},
                    }

                    if result.name == "direct_answer":
                        candidate = result.arguments.get("content", "").strip()
                        if candidate:
                            final_answer_text = candidate
                        elif all_sources:
                            # 已有检索结果但 LLM 选了 direct_answer（无 content），
                            # 强制基于已有上下文流式生成，避免丢失已召回的 sources。
                            # 展示已在上方统一标为 generate，此处不再重复 yield thinking。
                            final_messages = self._build_final_prompt(question, all_sources, messages)
                            full_answer = ""
                            async for delta in self.llm.stream_chat(final_messages):
                                full_answer += delta
                                yield {"event": "delta", "data": {"content": delta}}
                            final_answer_text = full_answer
                        else:
                            # 无任何检索结果时才走纯通用回答
                            quick_msgs = [
                                {"role": "system", "content": (
                                    "你是「知海 Knoa」，一个跨境电商运营知识助手。"
                                    "请简洁友好地回答用户的问题。不要自我介绍或罗列功能。"
                                ) + self._memory_section()},
                                {"role": "user", "content": question},
                            ]
                            try:
                                final_answer_text = await self.llm.chat(quick_msgs)
                            except Exception:
                                final_answer_text = "好的，收到！"
                        # 非流式路径（candidate 直接给内容 / 纯通用回答）才需一次性 yield；
                        # 流式路径（已逐 token 输出）由上方 `elif all_sources` 分支处理，不再重复。
                        if final_answer_text and (not all_sources or candidate):
                            yield {"event": "delta", "data": {"content": final_answer_text}}
                        break

                    elif result.name == "retrieve":
                        query = result.arguments.get("query", question)
                        retrieved = await self.retriever.retrieve(query, kb_id, top_k=5)
                        if retrieved:
                            sources = self._format_sources(retrieved)
                            all_sources.extend(sources)
                            yield {"event": "sources", "data": sources}
                            context_text = self._sources_to_context(retrieved)
                            messages.append({"role": "assistant", "content": f"[已调用检索 retrieve，针对「{query}」检索到 {len(retrieved)} 条相关文档]"})
                            messages.append({"role": "user", "content": f"检索结果：\n{context_text}\n\n基于以上信息，请直接给出最终回答。如果信息明显不足，才调用 supplement_search（大多数情况下直接回答即可）。"})
                            continue
                        else:
                            messages.append({"role": "assistant", "content": "[已调用 retrieve 工具，但未找到相关文档]"})
                            messages.append({"role": "user", "content": "检索未找到相关结果。请基于通用知识回答或尝试 supplement_search。"})
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
                            messages.append({"role": "assistant", "content": f"[已调用补充检索 supplement_search，针对「{gap}」检索到 {len(retrieved)} 条]"})
                            messages.append({"role": "user", "content": f"补充检索结果：\n{context_text}\n\n结合之前所有信息，请直接给出最终回答。"})
                            continue
                        else:
                            messages.append({"role": "assistant", "content": "[补充检索也未找到新结果]"})
                            messages.append({"role": "user", "content": "补充检索也没结果。请基于已有信息尽量回答。"})
                            continue
                    elif result.name == "web_search":
                        query = result.arguments.get("query", question)
                        searcher = WebSearcher()
                        try:
                            web = await searcher.search(query, max_results=5)
                        finally:
                            await searcher.aclose()
                        if web:
                            for i, w in enumerate(web, len(all_sources) + 1):
                                w["id"] = i
                                w["chunk_id"] = f"web:{i}"
                            all_sources.extend(web)
                            yield {"event": "sources", "data": self._format_sources(web)}
                            context_text = self._sources_to_context(web)
                            messages.append({"role": "assistant", "content": f"[已调用联网搜索 web_search，针对「{query}」检索到 {len(web)} 条网络结果]"})
                            messages.append({"role": "user", "content": f"联网搜索结果：\n{context_text}\n\n结合以上信息（含知识库与联网结果），请直接给出最终回答。"})
                            continue
                        else:
                            messages.append({"role": "assistant", "content": "[联网搜索未找到相关结果]"})
                            messages.append({"role": "user", "content": "联网搜索无结果。请基于已有信息尽量回答。"})
                            continue
                    else:
                        final_answer_text = f"抱歉，系统遇到了未知状态 ({result.name})。请重试。"
                        break

                # ── 循环结束后，若尚未得到答案则流式生成 ──
                if not final_answer_text:
                    if all_sources:
                        # 有检索结果但循环耗尽（MAX_STEPS）仍未给答案，基于上下文生成
                        yield {
                            "event": "thinking",
                            "data": {"step": step, "action": "generate",
                                     "detail": f"达到最大步数，基于 {len(all_sources)} 条结果生成回答",
                                     "raw_reasoning": ""},
                        }
                    final_messages = self._build_final_prompt(question, all_sources, messages)
                    full_answer = ""
                    async for delta in self.llm.stream_chat(final_messages):
                        full_answer += delta
                        yield {"event": "delta", "data": {"content": delta}}
                    final_answer_text = full_answer

            # ---- 持久化 + done ----
            if not final_answer_text.strip():
                final_answer_text = "抱歉，我暂时无法生成回答，请稍后重试。"
                yield {"event": "delta", "data": {"content": final_answer_text}}

            citations = self._extract_citations(final_answer_text)
            assistant_msg = ChatMessage(
                session_id=session.id, role="assistant",
                content=final_answer_text, citations=citations, sources=all_sources,
            )
            self.db.add(assistant_msg)
            await self.db.commit()

            # ── Mem0：后台抽取/保存长期记忆（不阻塞回答已返回的 SSE 流） ──
            if self.memory and self.user_id:
                try:
                    asyncio.create_task(self._save_memory(question, final_answer_text))
                except Exception:
                    pass

            yield {
                "event": "done",
                "data": {"messageId": str(assistant_msg.id), "citations": citations, "sessionId": str(session.id)},
            }

        except Exception as e:
            yield {"event": "error", "data": {"message": str(e)}}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _describe_action(self, result: ToolCallResult) -> str:
        if result.name == "direct_answer":
            return "判断为无需检索，直接回答"
        if result.name == "generate":
            return "基于检索结果生成回答"
        if result.name == "retrieve":
            q = result.arguments.get("query", "")[:60]
            reason = result.arguments.get("reason", "")[:40]
            return f"检索知识库：「{q}...」（{reason}）"
        if result.name == "supplement_search":
            q = result.arguments.get("refined_query", "")[:60]
            gap = result.arguments.get("gap_description", "")[:40]
            return f"补充检索：「{q}...」（{gap}）"
        if result.name == "web_search":
            q = result.arguments.get("query", "")[:60]
            reason = result.arguments.get("reason", "")[:40]
            return f"联网搜索：「{q}...」（{reason}）"
        return f"执行 {result.name}"

    def _format_sources(self, retrieved: list[dict]) -> list[dict]:
        return [
            SourceItemOut(
                id=r["id"], chunk_id=r["chunk_id"], kb=r["kb"],
                title=r["title"], snippet=r["snippet"],
                confidence=r.get("confidence", 0.0),
                source_type=r.get("source_type", "kb"),
                url=r.get("url"),
            ).model_dump(by_alias=True)
            for r in retrieved
        ]

    def _sources_to_context(self, retrieved: list[dict]) -> str:
        parts = []
        for r in retrieved:
            body = r.get("content") or r.get("snippet", "")
            parts.append(f"\n[{r['id']}] {r['title']} ({r['kb']})\n{body}")
        return "\n".join(parts)

    def _build_final_prompt(self, question: str, all_sources: list[dict], _) -> list[dict]:
        parts = []
        for i, s in enumerate(all_sources, 1):
            tag = "联网来源" if s.get("source_type") == "web" else "知识库"
            parts.append(f"\n[{i}] ({tag}) {s['title']}\n{s.get('snippet', '')}\n")
        context = "\n".join(parts)
        system = (
            "你是「知海 Knoa」，一个跨境电商运营知识助手。\n"
            "请基于以下来源（知识库 / 联网）回答用户问题，回答必须忠实于来源内容。\n\n"
            "引用规则：引用时使用 [1] [2] 这样的标注对应下方编号；"
            "若某来源标记为（联网来源），引用时可注明「据联网信息」。\n"
            "关键要求：来源资料里的「片段」通常已包含用户要的具体数据"
            "（如汇率、价格、日期、政策要点），请直接从片段中提取并呈现给用户，"
            "并标注对应编号；不要说「无法获取/无法访问数据」，因为数据已在上文给出。\n"
            "确实没有任何来源覆盖该问题时，再如实说明。\n\n"
            f"来源资料：\n{context}" + self._memory_section()
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": question}]

    @staticmethod
    def _extract_citations(text: str) -> list[int]:
        return sorted(set(int(m) for m in re.findall(r"\[(\d+)\]", text)))

    def _memory_section(self) -> str:
        """把召回的用户记忆格式化成可注入 system prompt 的文本块（无记忆则返回空串）。"""
        if not self._memories:
            return ""
        lines = ["\n\n## 用户长期记忆（来自历史对话，不与该用户显式意愿冲突时请优先遵循）"]
        for m in self._memories:
            lines.append(f"- {m}")
        return "\n".join(lines)

    async def _save_memory(self, question: str, answer: str) -> None:
        """问答结束后，后台抽取并保存长期记忆（不阻塞已返回的 SSE 流）。

        自己开一个独立 db session，与请求主 session 解耦，
        这样即便生成器已 yield done 并随请求关闭主 session，记忆落库仍可进行。
        """
        if not (self.memory and self.user_id):
            return
        # 打招呼 / 闲聊无需记忆，省一次 LLM 调用
        if _should_skip_retrieval(question):
            return
        try:
            async with AsyncSessionLocal() as s:
                memories = await self.memory.extract(self.llm, question, answer)
                if memories:
                    await self.memory.save(self.user_id, memories, s)
        except Exception as e:
            logger.warning("memory save failed (skipped): %s", e)

    async def _get_or_create_session(self, session_id: str | None, question: str) -> ChatSession:
        if session_id:
            result = await self.db.execute(select(ChatSession).where(ChatSession.id == uuid.UUID(session_id)))
            s = result.scalar_one_or_none()
            if s:
                return s
        s = ChatSession(title=question[:50])
        self.db.add(s)
        await self.db.flush()
        return s
