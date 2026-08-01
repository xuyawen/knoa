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
  - web_search：联网搜索实时/外部信息

性能优化：
  - 快速预分类：天气/时间/实时数据/纯数学等明显超出知识库范围的提问，
    直接走 direct_answer，跳过昂贵的 LLM tool_call 决策（省 15~40s/次）。
  - 心跳 ping：在每次 LLM 调用前推送 ping 事件，防止前端因长时间无数据而超时。

结构（Phase3 T2，LangGraph 风格，纯 stdlib 自实现）：
  - 节点 = 函数（_n_route / _n_retrieve / _n_supplement / _n_web_search / _n_generate / _n_finish / _n_start_skip）
  - 边 = 节点执行结束时写回的「下一节点名」（st.next）
  - 状态 = 共享的 _AgentState 对象（question / messages / all_sources / step ...）
  - 调度 = _run_agent_loop 的 while 循环按 st.next 派发；不依赖 langgraph 库。
  本质就是状态机：route 决策 → 检索类节点 ⇄ 回到 route「反思」→ 够了就 generate/finish 终态。

对外接口：
  async for event in agent.stream(question, kb_id, session_id):
      # event = {"event": "thinking"|"sources"|"delta"|"done"|"error"|"ping", "data": ...}
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.core.llm.base import ToolCallResult
from app.core.graph import GraphStore
from app.core.memory import MemoryStore
from app.core.rag.agent_prompts import (
    AGENT_SYSTEM_PROMPT,
    INTENT_PROMPT,
    TOOLS_SCHEMA,
    should_skip_retrieval,
    should_web_search,
)
from app.core.rag.agent_session import SessionMemoryMixin
from app.core.rag.retriever import HybridRetriever
from app.core.metrics import record_ask_trace
from app.core.rag.web_search import WebSearcher
from app.core.store.redis_store import RedisStore
from app.db import ChatMessage
from app.models.knowledge import SourceItemOut

logger = logging.getLogger(__name__)

# 后台任务引用集：持有 asyncio 任务到其完成，防止被 GC 静默取消
# （CPython 对无引用 task 可能在下次 GC 时取消）；任务完成后自动 discard，
# 集合不会无限增长。
_BACKGROUND_TASKS: set = set()


def _spawn_background(coro):
    """即发即弃的后台任务：持有引用 + 完成后自动清理，异常记入日志。"""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task

try:
    from langsmith import traceable
except ImportError:

    def traceable(**kwargs):
        def decorator(fn):
            return fn
        return decorator


class _AgentState:
    """LangGraph 风格的共享状态：节点读写它，边（下一节点名）决定流转。

    ponytail: 一个普通类承载全部循环可变状态，不引第三方状态库；
    节点函数按 st.next 名字派发，等价于「条件边」。
    """

    def __init__(self, question: str, kb_id: str | None):
        self.question = question
        self.kb_id = kb_id
        self.messages: list[dict] = []      # route 用到的 agent 对话上下文
        self.all_sources: list[dict] = []   # 已召回的全部来源（KB/图/联网），连续编号
        # 来源编号 → chunk 全文。all_sources 里是 SourceItemOut（只带 150 字
        # snippet，为的是 SSE/入库瘦身），生成回答时需用全文，另存这里。
        self.source_content: dict[int, str] = {}
        self.retrieval_attempted: bool = False  # 是否已执行过 KB 检索（无论有无结果）
        self.step = 0                         # 已执行的 route 步数（上限 MAX_STEPS）
        self.action = ""                      # 最近一次 route 决策的动作名
        self.route_result: ToolCallResult | None = None
        self.candidate = ""                   # direct_answer 直接给的内容
        self.final_answer_text = ""
        self.next = "__end__"                # 下一节点名；"__end__" 终止
        # web_search 后是否回到 route 再决策：agent 循环内=True，启发式直搜=False
        self.web_loop = True
        # 8.3/8.5：意图分类结果 + 是否触发图谱多跳推理
        self.intent: str = "simple"          # greeting | web_search | simple | complex
        self.use_multihop: bool = False       # complex 意图 → 图谱多跳推理
        self.graph_reasoning: str = ""        # 多跳推理链路文本（注入 final prompt）
        self.thinking_steps: list[dict] = []   # 决策链（thinking 事件累积），落库供历史回显


class AgenticRAGAgent(SessionMemoryMixin):
    """Agentic RAG 代理 — 用 LLM 驱动的决策闭环替代固定检索流程。

    会话持久化/记忆/滚动摘要方法由 SessionMemoryMixin 提供（agent_session.py）。
    """

    MAX_STEPS = 3
    # 上下文窗口：最近多少条历史消息注入 LLM（约 N/2 轮对话）
    MAX_HISTORY_MESSAGES = 20

    def __init__(
        self,
        retriever: HybridRetriever,
        llm,
        redis: RedisStore,
        db: AsyncSession,
        user_id: str | None = None,
        memory: "MemoryStore | None" = None,
        graph: "GraphStore | None" = None,
        dept_id: str | None = None,
    ):
        self.retriever = retriever
        self.llm = llm
        self.redis = redis
        self.db = db
        self.user_id = user_id
        self.dept_id = dept_id  # 提问人所属部门（热搜按部门分桶用）
        self.memory = memory
        self.graph = graph
        self._memories: list[str] = []  # 本轮召回的该用户长期记忆
        self._graph_chunks: list[dict] = []  # 本轮图检索召回的相关 chunk
        self._summary_text: str = ""  # 本轮会话的滚动摘要文本（注入 system）
        self._model_override: str | None = None  # 用户偏好模型（settings.preferred_model）
        # 模型配置（前端 ModelConfig 下发，单次请求内有效）
        self._gen_temperature: float | None = None
        self._gen_top_p: float | None = None
        self._gen_max_tokens: int | None = None
        self._top_k: int | None = None
        self._web_search_enabled: bool | None = None
        self._custom_system_prompt: str | None = None
        self._concise_mode: bool | None = None
        self._source_count: int | None = None
        self._web_provider: str | None = None

    async def _classify_intent(self, question: str, history_hint: str = "") -> "tuple[str, str] | None":
        """LLM 意图分类 + 检索 query 改写（一次调用两用）。

        返回 (intent, query)：intent ∈ greeting/web_search/simple/complex，
        query 为改写后的检索关键词（simple 快路跳过 route 决策时用它检索，
        替代原本 route LLM 的 query 改写能力，零额外成本）。
        history_hint：最近两轮对话纯文本，供分类器消解追问里的指代/省略。
        失败或返回空 → None，由调用方退化为正则启发式兜底（query 用原句）。
        用流式通道拿短输出，规避推理模型非流式 content 为空的老问题。
        """
        if not self.llm:
            return None
        try:
            user_msg = f"问题：{question}"
            if history_hint:
                user_msg = (
                    f"最近对话（供理解上下文、消解指代）：\n{history_hint}\n\n"
                    f"问题：{question}"
                )
            text = ""
            async for piece in self.llm.stream_chat(
                [
                    {"role": "system", "content": INTENT_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=60,
            ):
                text += piece
            return self._parse_intent_json(text, question)
        except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort fallback to heuristic intent)
            logger.warning("intent classify failed (fallback heuristic): %s", e)
            return None

    @staticmethod
    def _parse_intent_json(text: str, question: str) -> "tuple[str, str] | None":
        """三层兜底解析意图分类器输出：JSON → 正则抽标签 → None。

        分类器（小模型/短输出）偶尔吐格式不完整的 JSON 或退回纯标签，
        逐层降级保证不比现状差；query 解析失败一律退回原问题。
        """
        raw = text.strip()
        # 剥可能的 ```json 围栏（prompt 已禁止，防御性处理）
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            raw = raw.strip()
        # 第 1 层：严格 JSON
        try:
            obj = json.loads(raw)
            intent = str(obj.get("intent", "")).strip().lower()
            query = str(obj.get("query", "")).strip() or question
            if intent in ("greeting", "web_search", "complex", "simple"):
                return intent, query
        except (ValueError, AttributeError, TypeError):
            pass
        # 第 2 层：从杂乱文本里抽 JSON 片段
        m = re.search(
            r'\{[^{}]*"intent"\s*:\s*"(greeting|web_search|complex|simple)"[^{}]*\}',
            raw, re.I,
        )
        if m:
            intent = m.group(1).lower()
            qm = re.search(r'"query"\s*:\s*"([^"]*)"', raw)
            query = (qm.group(1).strip() if qm else "") or question
            return intent, query
        # 第 3 层：纯标签（兼容旧格式 / 模型只吐了标签）
        low = raw.lower()
        for label in ("greeting", "web_search", "complex", "simple"):
            if label in low:
                return label, question
        return None

    @staticmethod
    def _history_hint(raw_history: list[dict]) -> str:
        """取最近两轮对话拼成纯文本，供意图分类器消解追问的指代/省略。

        多模态 content blocks 只抽文本段（绝不塞 base64）；每条截断 120 字，
        控制分类调用的输入体积。
        """
        turns = [m for m in raw_history if m.get("role") in ("user", "assistant")]
        lines: list[str] = []
        for m in turns[-4:]:  # 最近两轮 = 至多 2 user + 2 assistant
            content = m.get("content")
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            content = (content or "").strip()
            if content:
                who = "用户" if m.get("role") == "user" else "助手"
                lines.append(f"{who}：{content[:120]}")
        return "\n".join(lines)

    @staticmethod
    def _heuristic_intent(question: str) -> str:
        """LLM 不可用时的兜底意图判断（保留问候/实时快路 + 关系类判 complex）。"""
        if should_web_search(question):
            return "web_search"
        # 含关系/对比/影响类措辞 → 视为复杂业务问题，触发图谱多跳推理
        if re.search(r"(关系|区别|差异|对比|影响|联系|关联|和.{1,6}的|与.{1,6}的|vs|VS|相对于|导致|因为)", question):
            return "complex"
        return "simple"

    async def _maybe_record_gap(self, db, kb_id: str, question: str) -> None:
        """知识缺口信号：图检索无命中且该 KB 有图谱节点 → 记录 gap。

        限流：同用户同 KB 60s 内不重复写。best-effort，失败不影响主流程。
        """
        try:
            from app.db import KGGapSignal, KGNode
            # 确认该 KB 有图谱节点（非空图）
            has_nodes = await db.scalar(select(KGNode.id).where(KGNode.kb_id == kb_id).limit(1))
            if not has_nodes:
                return
            # 限流：60s 内同用户同 KB 不重复写
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
            recent = await db.scalar(
                select(KGGapSignal.id).where(
                    KGGapSignal.kb_id == kb_id,
                    KGGapSignal.user_id == self.user_id,
                    KGGapSignal.created_at >= cutoff,
                ).limit(1)
            )
            if recent:
                return
            db.add(KGGapSignal(kb_id=kb_id, question=question[:500], user_id=self.user_id))
            await db.commit()
        except Exception as e:  # noqa: BLE001
            logger.debug("gap signal write skipped: %s", e)

    async def _suggest_title(self, session, question: str, answer: str) -> "str | None":
        """会话首轮问答时用 LLM 生成简洁标题（≤15 字），替代「问题前 50 字」默认标题。

        仅当这是会话第一轮问答且标题仍为系统默认（新对话 / 问题截断）时
        才重写，避免覆盖用户手动改过的标题。
        """
        if not self.llm or not answer.strip():
            return None
        cnt = await self.db.scalar(
            select(func.count()).select_from(ChatMessage).where(
                ChatMessage.session_id == session.id,
                ChatMessage.role == "assistant",
            )
        )
        if (cnt or 0) > 1:  # 非首轮问答（本轮回答已入库）→ 不重写
            return None
        await self.db.refresh(session)  # commit 后属性已过期，标题需重新加载
        current = (session.title or "").strip()
        if current not in ("", "新对话", question[:50]):
            return None
        try:
            text = ""
            async for piece in self.llm.stream_chat(
                [
                    {"role": "system", "content": "你是会话标题生成器。根据用户问题和AI回答，生成一个不超过15个字的简洁标题。直接输出标题文本，不要引号、标点或解释。"},
                    {"role": "user", "content": f"问题：{question[:100]}\n回答摘要：{answer[:200]}"},
                ],
                temperature=0.3,
                max_tokens=30,
            ):
                text += piece
            title = text.strip().strip('"\'“”‘’《》【】')
            return title[:30] or None
        except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort, keep default title on failure)
            logger.warning("session title generation failed: %s", e)
            return None

    async def _suggest_follow_ups(self, question: str, answer: str) -> list[str]:
        """基于本轮问答生成 2~3 个用户可能想继续追问的简短问题。

        前端用它们替换静态的「你可能还想问」，点击即发送。
        """
        if not self.llm or not answer.strip():
            return []
        try:
            text = ""
            async for piece in self.llm.stream_chat(
                [
                    {"role": "system", "content": "你是追问建议生成器。根据用户提问和AI回答，生成3个用户可能想继续追问的简短问题。每行一个问题，不要编号、不要引号、不要解释，每个问题不超过25个字。"},
                    {"role": "user", "content": f"问题：{question[:100]}\n回答摘要：{answer[:300]}"},
                ],
                temperature=0.5,
                max_tokens=120,
            ):
                text += piece
            out: list[str] = []
            for line in text.splitlines():
                q = re.sub(r"^[\s\d.\-*、）)]+", "", line.strip()).strip('"\'“”‘’')
                if q and 4 <= len(q) <= 40 and q not in out:
                    out.append(q)
                if len(out) >= 3:
                    break
            return out
        except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort, frontend falls back to static suggestions)
            logger.warning("follow-up generation failed: %s", e)
            return []

    @traceable(name="agentic_rag_stream", tags=["agent", "rag"])
    async def stream_answer(
        self,
        question: str,
        kb_id: str | None = None,
        session_id: str | None = None,
        files: "list[dict] | None" = None,
        model: str | None = None,
        # ── 模型配置（前端 ModelConfig 页下发；None=用后端默认）──
        temperature: "float | None" = None,
        top_p: "float | None" = None,
        top_k: "int | None" = None,
        web_search: "bool | None" = None,
        system_prompt: "str | None" = None,
        concise_mode: "bool | None" = None,
        max_tokens: "int | None" = None,
        source_count: "int | None" = None,
        web_provider: "str | None" = None,
    ) -> AsyncIterator[dict]:
        """主入口：返回 SSE 兼容的事件流。

        model: 用户偏好模型（settings.preferred_model）透传，覆盖实例默认；
        为空则用 config.LLM_MODEL。意图分类/滚动摘要等内部短调用仍走默认模型。
        """
        self._model_override = model
        self._gen_temperature = temperature
        self._gen_top_p = top_p
        self._gen_max_tokens = max_tokens
        self._top_k = top_k
        self._web_search_enabled = web_search
        self._custom_system_prompt = system_prompt
        self._concise_mode = concise_mode
        self._source_count = source_count
        self._web_provider = web_provider
        t0 = time.perf_counter()
        intent = "simple"
        retrieved = 0
        graph_used = False
        try:
            # ---- 会话 & 持久化 ----
            session = await self._get_or_create_session(session_id, question)
            self.db.add(
                ChatMessage(
                    session_id=session.id,
                    role="user",
                    content=question,
                    attachments=files,  # 多模态:图片 base64 等存 JSONB,供历史回显
                )
            )
            await self.db.flush()
            # 提前提交「会话 + 用户消息」：保证「用户已提问」这一事实在 LLM 生成前就落库。
            # 否则一旦后续检索/生成环节抛异常，整段未提交事务会在 get_db 的
            # db.close() 时回滚（asyncpg 行为），用户刚问的对话会从历史里凭空消失——
            # 回复靠 SSE 已推到前端内存所以「看起来完整」，但库里查无此会话。
            # 提前提交后，即使生成失败，会话与用户问题仍在，最多只丢回答。
            await self.db.commit()

            # ponytail: 只统计真实业务提问，过滤打招呼/闲聊/天气等，避免污染“高频问题”
            if not should_skip_retrieval(question):
                try:
                    await self.redis.incr_trending(question, self.dept_id)
                except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, don't fail request if trending counter update fails)
                    pass

            all_sources: list[dict] = []
            source_content: dict[int, str] = {}  # 编号 → chunk 全文（生成时注入）
            final_answer_text: str = ""
            graph_reasoning_text: str = ""  # 8.5 多跳推理链路，注入 final prompt
            pre_loop_thinking: list[dict] = []  # 循环前产出的 thinking 事件（落库用）
            skip = should_skip_retrieval(question)

            # ── 加载会话历史 + 滚动摘要（提前到三路并行之前）──
            # 意图分类器需要最近两轮上下文来改写检索 query（消解追问里的
            # 「这个/那个」指代），故历史必须先于三路并行就绪；摘要文本
            # 同样在此处装配进 system prompt。
            raw_history, summary = await self._load_session_history(session)
            self._summary_text = summary or ""
            history_hint = self._history_hint(raw_history)

            # ── 三路并行：Mem0 记忆召回 / 8.3 意图分类 / 图谱相关 chunk 检索 ──
            # 三者互不依赖，串行会白白浪费一次 LLM 往返的延迟（意图分类是
            # 完整 LLM 调用）。注意 AsyncSession 不支持并发复用，memory 与
            # graph 各用独立会话；意图分类是纯 LLM 调用，不依赖 DB。
            async def _mem_task() -> list[str]:
                if not (self.memory and self.user_id and settings.MEMORY_ENABLED):
                    return []
                try:
                    async with AsyncSessionLocal() as mdb:
                        return await self.memory.retrieve(
                            self.user_id, question, mdb, settings.MEMORY_TOP_K
                        )
                except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort, skip memory injection if retrieve fails)
                    logger.warning("memory retrieve failed (skip inject): %s", e)
                    return []

            async def _intent_task() -> "tuple[str, str]":
                # 纯 trivial（打招呼/数学/时间）直接 greeting 快路，不浪费 LLM 调用；
                # 其余业务问题才调 LLM 分类（顺带改写检索 query），失败退化为
                # 正则启发式（query 用原句，保留问候/实时兜底）。
                if skip:
                    return "greeting", question
                if settings.INTENT_ENABLED:
                    classified = await self._classify_intent(question, history_hint)
                    if classified is not None:
                        return classified
                return self._heuristic_intent(question), question

            async def _graph_task() -> list[dict]:
                # Graph RAG：图感知检索，把实体关系相关的 chunk 也拉进来当来源；
                # 仅对真实业务问题生效（跳过打招呼/闲聊），kb_id 为空也跳过。
                if not (self.graph and settings.GRAPH_ENABLED and kb_id and not skip):
                    return []
                try:
                    async with AsyncSessionLocal() as gdb:
                        chunks = await self.graph.retrieve_related_chunks(
                            question, kb_id, gdb, settings.GRAPH_TOP_K
                        )
                        # 知识缺口信号：图检索返回空 且 该 KB 有图谱节点（非空图）→ 记录 gap
                        if not chunks and self.user_id:
                            await self._maybe_record_gap(gdb, kb_id, question)
                        return chunks
                except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort, skip graph enrichment if it fails)
                    logger.warning("graph retrieve failed (skip inject): %s", e)
                    return []

            self._memories, (intent, rewritten_query), graph_chunks = await asyncio.gather(
                _mem_task(), _intent_task(), _graph_task()
            )
            use_multihop = intent == "complex"

            # ── 并行召回的图谱相关 chunk 暂存，等 _n_retrieve 合并 rerank ──
            if graph_chunks:
                self._graph_chunks = graph_chunks

            # ── 8.5 complex 意图 → 图谱多跳推理，产出推理链路 + 追加沿途来源 ──
            if use_multihop and self.graph and settings.GRAPH_ENABLED and kb_id and not skip:
                try:
                    chains, mh_chunks = await self.graph.multi_hop_reason(
                        question, kb_id, self.db, settings.GRAPH_MULTI_HOP_MAX
                    )
                    if chains:
                        graph_reasoning_text = "\n".join(chains)
                        _think_ev = {
                            "step": 0, "action": "graph_reason",
                            "detail": f"图谱多跳推理链路（{len(chains)} 条）",
                            "raw_reasoning": "",
                        }
                        pre_loop_thinking.append(_think_ev)
                        yield {"event": "thinking", "data": _think_ev}
                    # 注意：all_sources 里是格式化后的 dict（键为 camelCase
                    # chunkId），此前误用 snake_case chunk_id 取值恒为 None，
                    # 去重形同虚设，多跳与图检索的重叠 chunk 会被重复入选
                    existing_ids = {s.get("chunkId") for s in all_sources}
                    for c in mh_chunks:
                        if c["chunk_id"] not in existing_ids:
                            c["id"] = len(all_sources) + 1
                            source_content[c["id"]] = c.get("content") or c.get("snippet", "")
                            all_sources.extend(self._format_sources([c]))
                            existing_ids.add(c["chunk_id"])
                    if mh_chunks:
                        yield {"event": "sources", "data": list(all_sources)}
                except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort, skip graph enrichment if it fails)
                    logger.warning("graph multihop failed (skip inject): %s", e)

            # ── 构造共享状态 + 选择入口节点（LangGraph 的 start 边）──
            # 多模态:把文本 + 图片拼成 OpenAI 多模态 content blocks
            # (纯文本 → str;带图 → list)。agent 决策(tool_call)也能看到图。
            user_content = self._build_user_content(question, files)
            st = _AgentState(question, kb_id)
            st.thinking_steps = pre_loop_thinking  # 合并循环前的 thinking 事件
            st.all_sources = all_sources
            st.source_content = source_content
            st.intent = intent
            st.use_multihop = use_multihop
            st.graph_reasoning = graph_reasoning_text

            # ── 会话历史已在三路并行前加载（供意图分类改写 query），此处仅装配决策上下文 ──
            st.messages = [
                {"role": "system", "content": self._build_system_prompt()},
                *raw_history,
                {"role": "user", "content": user_content},
            ]
            if files:
                # 带图必须让 LLM 亲眼看,不走问候/常识快路(即使问题像打招呼)
                st.next = "_n_route"
            elif intent == "greeting":
                st.next = "_n_start_skip"          # 问候/常识 → 直接友好回答
            elif intent == "web_search":
                if self._web_search_enabled is False:
                    # 用户关闭联网 → 退化为 simple 快路，走知识库检索
                    intent = "simple"
                    self._arm_simple_route(st, rewritten_query)
                    st.next = "_n_start_simple"
                else:
                    st.web_loop = False
                    st.next = "_n_web_search"      # 实时信息 → 搜一次即生成
            elif intent == "simple":
                # simple 快路：跳过 route LLM 决策，直接用改写后的 query 检索
                # （意图分类已零成本产出检索词，省一次完整 tool_call 往返）
                self._arm_simple_route(st, rewritten_query)
                st.next = "_n_start_simple"
            else:
                st.next = "_n_route"               # complex 业务问题 → agent 决策循环

            # ── 跑图：按 st.next 派发节点，直到 __end__ ──
            async for ev in self._run_agent_loop(st):
                # ponytail: 累积 thinking 事件，供 assistant 落库（历史回显决策链）
                if ev.get("event") == "thinking":
                    st.thinking_steps.append(ev.get("data", {}))
                yield ev
            final_answer_text = st.final_answer_text

            # ---- 持久化 + done ----
            if not final_answer_text.strip():
                final_answer_text = "抱歉，我暂时无法生成回答，请稍后重试。"
                yield {"event": "delta", "data": {"content": final_answer_text}}

            citations = self._extract_citations(final_answer_text)
            assistant_msg = ChatMessage(
                session_id=session.id, role="assistant",
                content=final_answer_text, citations=citations, sources=st.all_sources,
                thinking_steps=st.thinking_steps or None,
            )
            self.db.add(assistant_msg)
            await self.db.commit()

            # ── Mem0：后台抽取/保存长期记忆（不阻塞回答已返回的 SSE 流） ──
            # 持有 task 引用到完成，避免被 GC 静默取消；异常记入日志而非吞掉
            if self.memory and self.user_id:
                _spawn_background(self._save_memory(question, final_answer_text))

            # ── 滚动摘要：后台压缩窗口外旧对话（不阻塞 SSE 流，下一轮才生效） ──
            _spawn_background(self._roll_summary(session.id))

            # ── 问答链路追踪：耗时 + 召回块数 + 是否触发图谱 + 意图 + 模型 ──
            intent = st.intent
            retrieved = len(st.all_sources)
            graph_used = st.use_multihop
            record_ask_trace(
                latency=time.perf_counter() - t0,
                retrieved=retrieved,
                graph_used=graph_used,
                intent=intent,
                model=self._model_override or settings.LLM_MODEL,
                tokens_est=max(0, len(final_answer_text) // 2),
                is_error=False,
            )

            yield {
                "event": "done",
                "data": {"messageId": str(assistant_msg.id), "citations": citations, "sessionId": str(session.id)},
            }

            # ── 答后增强：会话简洁标题（仅首轮改写）+ 相关追问建议 ──
            # 两个短 LLM 调用并行执行；放在 done 之后以独立 follow_ups 事件
            # 下发，不阻塞 done（其携带 messageId）；失败静默降级，绝不影响
            # 已答完的流。打招呼/闲聊类提问不生成。
            if not skip:
                try:
                    new_title, follow_ups = await asyncio.gather(
                        self._suggest_title(session, question, final_answer_text),
                        self._suggest_follow_ups(question, final_answer_text),
                    )
                    if new_title:
                        session.title = new_title
                        await self.db.commit()
                    if new_title or follow_ups:
                        yield {
                            "event": "follow_ups",
                            "data": {"questions": follow_ups, "sessionTitle": new_title},
                        }
                except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort enhancement, never fail the answered stream)
                    logger.warning("follow_ups/title generation failed: %s", e)

        except Exception as e:  # noqa: BLE001  (intentional catch-all: top-level guard, convert any answer-stream error into an SSE error event)
            logger.exception("stream_answer failed")
            record_ask_trace(
                latency=time.perf_counter() - t0,
                retrieved=retrieved,
                graph_used=graph_used,
                intent=intent,
                model=self._model_override or settings.LLM_MODEL,
                tokens_est=0,
                is_error=True,
            )
            # 对外只暴露可控文案：HTTPException.detail 是自己写的中文提示可直出；
            # 其余异常的内部细节（连接串/堆栈/上游报错）只进日志，防止经 SSE 泄漏
            msg = e.detail if isinstance(e, HTTPException) else "服务暂时出现问题，请稍后重试"
            yield {"event": "error", "data": {"message": msg}}

    # ------------------------------------------------------------------
    # LangGraph 风格图：节点 = 函数，边 = 返回的下一节点名，状态 = _AgentState
    # ------------------------------------------------------------------

    async def _run_agent_loop(self, st: "_AgentState") -> AsyncIterator[dict]:
        """按 st.next 派发节点的调度器（等价于 LangGraph 的编译后 graph.invoke）。"""
        while st.next != "__end__":
            node = getattr(self, st.next)
            async for ev in node(st):
                yield ev

    async def _n_route(self, st: "_AgentState") -> AsyncIterator[dict]:
        """决策节点：调 LLM 判断动作，并把「反思」结果（route）作为边回到检索或走向终态。"""
        st.step += 1
        yield {"event": "ping", "data": {"ts": time.time(), "step": st.step}}

        result: ToolCallResult = await self.llm.tool_call(
            st.messages, tools=TOOLS_SCHEMA, temperature=0.2
        )

        # 动作名归一化
        name = result.name
        if name == "web_search":
            # 用户关闭联网搜索 → 强制改为知识库检索（避免无来源空答）
            if self._web_search_enabled is False:
                name = "retrieve"
                result = ToolCallResult(
                    name="retrieve",
                    arguments={"query": st.question},
                    raw_text=result.raw_text,
                )
            # 否则已是正确动作，跳过归一化
        elif name not in (
            "retrieve", "supplement_search", "direct_answer",
            "query_documents", "document_detail", "kb_stats",
        ):
            if "query" in result.arguments:
                name = "retrieve"
            elif "refined_query" in result.arguments:
                name = "supplement_search"
            elif "sort_by" in result.arguments or "limit" in result.arguments:
                name = "query_documents"
            elif "title" in result.arguments:
                name = "document_detail"
            elif "time_range" in result.arguments:
                name = "kb_stats"
            elif "content" in result.arguments:
                name = "direct_answer"
            else:
                name = "direct_answer"
            result = ToolCallResult(
                name=name,
                arguments=result.arguments,
                raw_text=result.raw_text,
            )

        st.route_result = result
        st.action = name

        action_desc = self._describe_action(result)
        # ponytail: direct_answer 但已有检索结果时，实为「基于检索生成」，
        # 在前端就标成 generate，避免误导用户以为「没检索就回答」。
        display_action = name
        display_detail = action_desc
        if name == "direct_answer" and st.all_sources:
            display_action = "generate"
            display_detail = f"检索结果已充足（{len(st.all_sources)} 条），生成回答"

        yield {
            "event": "thinking",
            "data": {"step": st.step, "action": display_action,
                     "detail": display_detail,
                     "raw_reasoning": (result.raw_text or "")[:500]},
        }

        if name == "direct_answer":
            # ── 简化确定性规则（无嵌套、无歧义）──
            #
            # 规则1: 纯闲聊/数学/时间 且 从未检索过 → 允许直接答，结束
            # 规则2: 已检索过（有结果或无结果）→ 强制 _generate，绝不回路由（防死循环）
            # 规则3: 其他情况 → 强制 _retrieve，查完再说
            #
            # 关键设计：一旦进入过 _n_retrieve，后续永远不再回 _n_route，
            # 直接去 _n_generate 收尾。LLM 的路由选择只在首次生效。
            is_greeting_or_math = (
                should_skip_retrieval(st.question)
                or bool(re.match(r'^[你好嗨嘿哈哟哇噢唉哼啊嗯哦\s\,\.\!\?\~\@\#\$\%\^\&\*\(\)]+$', st.question.strip()))
            )

            if is_greeting_or_math and not st.retrieval_attempted:
                # 规则1: 纯 trivial 且从未检索 → 放行，走 _n_finish 结束
                st.candidate = result.arguments.get("content", "").strip()
                st.next = "_n_finish"

            elif st.retrieval_attempted:
                # 规则2: 已经检索过了（不管有没有结果）→ 永远走 generate，不回路由
                has_sources = bool(st.all_sources)
                detail_text = (
                    f"系统拦截：已找到 {len(st.all_sources)} 条检索结果，基于结果生成回答"
                    if has_sources
                    else "系统拦截：已检索但未找到相关文档，请如实告知用户"
                )
                st.route_result = ToolCallResult(name="generate", arguments={}, raw_text=result.raw_text)
                st.action = "generate"
                yield {
                    "event": "thinking",
                    "data": {"step": st.step, "action": "generate",
                             "detail": detail_text,
                             "raw_reasoning": (result.raw_text or "")[:500]},
                }
                st.next = "_n_generate"

            else:
                # 规则3: 从未检索且不是 trivial → 强制先检索
                st.route_result = ToolCallResult(
                    name="retrieve",
                    arguments={"query": st.question},
                    raw_text=result.raw_text,
                )
                st.action = "retrieve"
                yield {
                    "event": "thinking",
                    "data": {"step": st.step, "action": "retrieve",
                             "detail": f"系统拦截：原计划直接回答，已强制改为检索（问题: {st.question[:40]}）",
                             "raw_reasoning": (result.raw_text or "")[:500]},
                }
                st.next = "_n_retrieve"
        elif name == "retrieve":
            st.next = "_n_retrieve"
        elif name == "supplement_search":
            st.next = "_n_supplement"
        elif name == "web_search":
            st.next = "_n_web_search"
        elif name == "query_documents":
            st.next = "_n_query_documents"
        elif name == "document_detail":
            st.next = "_n_document_detail"
        elif name == "kb_stats":
            st.next = "_n_kb_stats"
        else:
            st.next = "_n_generate"

        # 步数上限：达到 MAX_STEPS 仍选了检索类动作 → 强制生成，保证终止
        if st.step >= self.MAX_STEPS and st.next in (
            "_n_retrieve", "_n_supplement", "_n_web_search",
            "_n_query_documents", "_n_document_detail", "_n_kb_stats",
        ):
            yield {
                "event": "thinking",
                "data": {"step": st.step, "action": "generate",
                         "detail": f"达到最大步数，基于 {len(st.all_sources)} 条结果生成回答",
                         "raw_reasoning": ""},
            }
            st.next = "_n_generate"

    async def _n_retrieve(self, st: "_AgentState") -> AsyncIterator[dict]:
        st.retrieval_attempted = True
        query = st.route_result.arguments.get("query", st.question)
        top_k = self._top_k or settings.RAG_TOP_K
        retrieved = await self.retriever.retrieve(query, st.kb_id, top_k=top_k)

        # ── 图谱 chunk 合并 + 统一 rerank ──
        # 把暂存的图谱检索结果与向量检索结果合并，按 chunk_id 去重，
        # 然后一起过 reranker，保证两路来源统一排序。
        if self._graph_chunks:
            existing_cids = {r["chunk_id"] for r in retrieved}
            for gc in self._graph_chunks:
                if gc["chunk_id"] not in existing_cids:
                    retrieved.append(gc)
                    existing_cids.add(gc["chunk_id"])
            # 统一 rerank（如果 reranker 启用）
            if hasattr(self.retriever, 'reranker') and self.retriever.reranker.enabled and len(retrieved) > 1:
                candidates = [
                    {
                        "cid": r["chunk_id"],
                        "content": r.get("content") or r.get("snippet", ""),
                        "vector_score": r.get("confidence", 0.5),
                        "bm25_score": 0.0,
                    }
                    for r in retrieved
                ]
                reranked = self.retriever.reranker.rerank(query, candidates, top_k)
                reranked_cids = [c["cid"] for c in reranked]
                by_cid = {r["chunk_id"]: r for r in retrieved}
                retrieved = [by_cid[cid] for cid in reranked_cids if cid in by_cid]
            self._graph_chunks = []  # 消费完毕，清空避免重复注入

        # 去重：图谱预检索/补充检索可能已命中相同 chunk，重复入选会撑大引用
        # 列表与上下文（同一原文占两个角标）。按 chunk_id 过滤。
        existing = {s.get("chunkId") for s in st.all_sources}
        retrieved = [r for r in retrieved if r["chunk_id"] not in existing]
        if retrieved:
            # 连续编号，接在已有来源（图/联网预检索）之后，
            # 避免与图谱预检索已占用的 1..N 撞号导致引用错位
            for i, r in enumerate(retrieved, len(st.all_sources) + 1):
                r["id"] = i
                st.source_content[i] = r.get("content") or r.get("snippet", "")
            st.all_sources.extend(self._format_sources(retrieved))
            yield {"event": "sources", "data": list(st.all_sources)}
            st.messages.append({"role": "assistant", "content": f"[已调用检索 retrieve，针对「{query}」检索到 {len(retrieved)} 条相关文档]"})
            # 全文经 source_content 在 _n_generate 统一注入一次，这里不再复述，
            # 避免同一批原文在上下文里出现两次（检索消息 + 来源资料）白费 token
            st.messages.append({"role": "user", "content": "检索已完成。请基于来源资料直接给出最终回答。"})
        else:
            st.messages.append({"role": "assistant", "content": "[已调用 retrieve 工具，但未找到相关文档]"})
            st.messages.append({"role": "user", "content": "检索未找到相关结果。请基于已有信息生成回答。"})
        # 检索完成后直接去 generate，不再回路由（防止 LLM 反复选 direct_answer 导致死循环）
        st.next = "_n_generate"

    async def _n_supplement(self, st: "_AgentState") -> AsyncIterator[dict]:
        refined_query = st.route_result.arguments.get("refined_query", st.question)
        gap = st.route_result.arguments.get("gap_description", "")
        top_k = self._top_k or settings.RAG_TOP_K
        retrieved = await self.retriever.retrieve(refined_query, st.kb_id, top_k=top_k)
        # 同 _n_retrieve：按 chunk_id 去重，不重复收录已命中的 chunk
        existing = {s.get("chunkId") for s in st.all_sources}
        retrieved = [r for r in retrieved if r["chunk_id"] not in existing]
        if retrieved:
            # 同 _n_retrieve：连续编号 + 记录全文，避免与已有来源撞号
            for i, r in enumerate(retrieved, len(st.all_sources) + 1):
                r["id"] = i
                st.source_content[i] = r.get("content") or r.get("snippet", "")
            st.all_sources.extend(self._format_sources(retrieved))
            yield {"event": "sources", "data": list(st.all_sources)}
            context_text = self._sources_to_context(retrieved)
            # 补充检索是唯一会回到 route 反思的路径：route 需要看到内容才能
            # 判断「够不够」，故这里保留全文（与 _n_generate 的来源资料有意重复一轮）
            st.messages.append({"role": "assistant", "content": f"[已调用补充检索 supplement_search，针对「{gap}」检索到 {len(retrieved)} 条]"})
            st.messages.append({"role": "user", "content": f"补充检索结果：\n{context_text}\n\n结合之前所有信息，请直接给出最终回答。"})
        else:
            st.messages.append({"role": "assistant", "content": "[补充检索也未找到新结果]"})
            st.messages.append({"role": "user", "content": "补充检索也没结果。请基于已有信息尽量回答。"})
        st.next = "_n_route"

    async def _n_web_search(self, st: "_AgentState") -> AsyncIterator[dict]:
        # 防御：用户关闭联网时（理论上入口/route 已拦截），兜底转知识库生成
        if self._web_search_enabled is False:
            st.messages.append({"role": "user", "content": "注意：联网搜索已关闭，请仅基于已有知识库资料回答。"})
            st.next = "_n_generate" if st.retrieval_attempted else "_n_route"
            return
        # 兼容两条入口：agent 循环内（route_result 已设置，取 arguments.query）
        # 与启发式直搜（should_web_search 直接进本节点，route_result 为 None，退用原问题）
        query = st.route_result.arguments.get("query", st.question) if st.route_result else st.question
        searcher = WebSearcher()
        try:
            web = await searcher.search(query, max_results=self._source_count or 5, provider=self._web_provider)
        finally:
            await searcher.aclose()
        if web:
            # 重新连续编号，接在 all_sources 之后，避免与知识库来源（1..N）撞号
            for i, w in enumerate(web, len(st.all_sources) + 1):
                w["id"] = i
                w["chunk_id"] = f"web:{i}"
                st.source_content[i] = w.get("content") or w.get("snippet", "")
            # 入库必须用格式化后的 camelCase dict（与 KB 来源一致），
            # 此前直接 extend 原始 snake_case dict，检索记录页按 sourceType
            # 统计联网来源时永远计不上
            st.all_sources.extend(self._format_sources(web))
            yield {"event": "sources", "data": list(st.all_sources)}
            context_text = self._sources_to_context(web)
            st.messages.append({"role": "assistant", "content": f"[已调用联网搜索 web_search，针对「{query}」检索到 {len(web)} 条网络结果]"})
            st.messages.append({"role": "user", "content": f"联网搜索结果：\n{context_text}\n\n结合以上信息（含知识库与联网结果），请直接给出最终回答。"})
        else:
            st.messages.append({"role": "assistant", "content": "[联网搜索未找到相关结果]"})
            st.messages.append({"role": "user", "content": "联网搜索无结果。请基于已有信息尽量回答。"})
        # 启发式直搜路径（web_loop=False）搜完即生成；agent 循环内则回到 route 再决策
        st.next = "_n_route" if st.web_loop else "_n_generate"

    async def _n_query_documents(self, st: "_AgentState") -> AsyncIterator[dict]:
        """查询文档元数据（标题、时间、状态），按时间排序。用于「最近新增」类问题。"""
        from app.db import Document, KnowledgeBase

        args = st.route_result.arguments
        sort_by = args.get("sort_by", "created_at")
        order = args.get("order", "desc")
        limit = min(args.get("limit", 10), 30)  # 硬上限 30

        # 构建查询：仅查当前 KB 的已审核文档
        sort_col = getattr(Document, sort_by, Document.created_at)
        order_expr = sort_col.desc() if order == "desc" else sort_col.asc()

        stmt = (
            select(
                Document.id,
                Document.title,
                Document.created_at,
                Document.updated_at,
                Document.uploader_name,
                Document.status,
                KnowledgeBase.name.label("kb_name"),
            )
            .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
            .where(Document.kb_id == st.kb_id)
            .where(Document.status == "已审核")
            .order_by(order_expr)
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()

        if rows:
            # 拼成 LLM 可理解的列表格式
            lines = []
            for r in rows:
                created = r.created_at.strftime("%Y-%m-%d") if r.created_at else "未知"
                updated = r.updated_at.strftime("%Y-%m-%d") if r.updated_at else ""
                uploader = r.uploader_name or "未知"
                date_part = f"上传: {created}"
                if updated and updated != created:
                    date_part += f" | 更新: {updated}"
                lines.append(f"- {r.title} [{r.kb_name}] ({date_part}, 上传人: {uploader})")
            summary = f"查询到 {len(rows)} 篇文档（按 {sort_by} {order}）：\n" + "\n".join(lines)
            st.messages.append({"role": "assistant", "content": f"[已调用 query_documents，查询到 {len(rows)} 篇文档]"})
            st.messages.append({"role": "user", "content": f"文档列表查询结果：\n{summary}\n\n请基于以上列表回答用户的问题。"})
        else:
            st.messages.append({"role": "assistant", "content": "[已调用 query_documents，当前知识库无符合条件的文档]"})
            st.messages.append({"role": "user", "content": "文档列表查询无结果。请告知用户当前知识库暂无文档。"})
        # 查完直接生成
        st.next = "_n_generate"

    async def _n_document_detail(self, st: "_AgentState") -> AsyncIterator[dict]:
        """按标题模糊匹配获取文档完整内容或摘要。"""
        from app.db import Document

        args = st.route_result.arguments
        title = args.get("title", "")
        mode = args.get("mode", "summary")

        # 按标题模糊匹配（ILIKE），取当前 KB 的已审核文档
        stmt = (
            select(Document.id, Document.title, Document.content_md,
                   Document.created_at, Document.updated_at, Document.uploader_name)
            .where(Document.kb_id == st.kb_id)
            .where(Document.status == "已审核")
            .where(Document.title.ilike(f"%{title}%"))
            .order_by(Document.created_at.desc())
            .limit(1)
        )
        row = (await self.db.execute(stmt)).first()

        if row:
            created = row.created_at.strftime("%Y-%m-%d") if row.created_at else "未知"
            updated = row.updated_at.strftime("%Y-%m-%d") if row.updated_at else ""
            uploader = row.uploader_name or "未知"
            meta = f"文档: {row.title}\n上传: {created}"
            if updated and updated != created:
                meta += f" | 更新: {updated}"
            meta += f" | 上传人: {uploader}"

            content = row.content_md or "（文档内容为空）"
            if mode == "summary" and len(content) > 3000:
                # summary 模式截断前 3000 字符，避免 LLM 上下文爆炸
                content = content[:3000] + "\n...(内容过长已截断，如需完整内容请前往文档详情页查看)"

            st.messages.append({"role": "assistant", "content": f"[已调用 document_detail，找到文档「{row.title}」]"})
            st.messages.append({"role": "user", "content": f"{meta}\n\n文档内容：\n{content}\n\n请基于以上文档内容回答用户的问题。"})
        else:
            st.messages.append({"role": "assistant", "content": f"[已调用 document_detail，未找到标题包含「{title}」的文档]"})
            st.messages.append({"role": "user", "content": f"未找到标题包含「{title}」的文档。请告诉用户当前知识库中没有这篇文档，可以换用 retrieve 搜索相关内容。"})
        st.next = "_n_generate"

    async def _n_kb_stats(self, st: "_AgentState") -> AsyncIterator[dict]:
        """查询知识库统计概览：文档数、新增趋势、审核率、活跃贡献者。"""
        from datetime import timedelta
        from app.db import Document, KnowledgeBase

        args = st.route_result.arguments
        days = min(args.get("time_range", 30), 365)  # 硬上限 1 年
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # 如果指定了 kb_id，只查当前 KB；否则查当前用户可见的全部
        kb_filter = [Document.kb_id == st.kb_id] if st.kb_id else []

        # 1) 文档总数 + 审核数
        total_stmt = (
            select(
                func.count(Document.id).label("total"),
                func.count(Document.id).filter(Document.status == "已审核").label("approved"),
                func.count(Document.id).filter(Document.status == "待复核").label("pending"),
                func.count(Document.id).filter(Document.created_at >= since).label("recent"),
            )
            .where(*kb_filter)
        )
        total_row = (await self.db.execute(total_stmt)).first()

        # 2) 活跃贡献者 TOP5
        contributor_stmt = (
            select(
                Document.uploader_name,
                func.count(Document.id).label("cnt"),
            )
            .where(*kb_filter)
            .where(Document.uploader_name.isnot(None))
            .group_by(Document.uploader_name)
            .order_by(func.count(Document.id).desc())
            .limit(5)
        )
        contributors = (await self.db.execute(contributor_stmt)).all()

        # 3) 各知识库文档数
        kb_breakdown_stmt = (
            select(
                KnowledgeBase.name,
                func.count(Document.id).label("cnt"),
                func.count(Document.id).filter(Document.created_at >= since).label("recent"),
            )
            .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
            .where(*kb_filter)
            .group_by(KnowledgeBase.name)
            .order_by(func.count(Document.id).desc())
        )
        kb_breakdown = (await self.db.execute(kb_breakdown_stmt)).all()

        # 拼装报告
        total = total_row.total or 0
        approved = total_row.approved or 0
        pending = total_row.pending or 0
        recent = total_row.recent or 0
        review_rate = f"{approved / total * 100:.0f}%" if total > 0 else "N/A"

        lines = [
            f"📊 知识库统计概览（近 {days} 天）：",
            f"- 文档总数: {total}（已审核: {approved}，待复核: {pending}）",
            f"- 审核率: {review_rate}",
            f"- 近期新增: {recent} 篇",
        ]

        if contributors:
            lines.append(f"- 活跃贡献者 TOP5:")
            for c in contributors:
                lines.append(f"  · {c.uploader_name}: {c.cnt} 篇")

        if kb_breakdown:
            lines.append(f"- 各知识库分布:")
            for kb in kb_breakdown:
                recent_tag = f"（近期 +{kb.recent}）" if kb.recent else ""
                lines.append(f"  · {kb.name}: {kb.cnt} 篇{recent_tag}")

        report = "\n".join(lines)
        st.messages.append({"role": "assistant", "content": "[已调用 kb_stats，已生成统计报告]"})
        st.messages.append({"role": "user", "content": f"知识库统计结果：\n{report}\n\n请基于以上统计数据回答用户的问题。"})
        st.next = "_n_generate"

    async def _n_generate(self, st: "_AgentState") -> AsyncIterator[dict]:
        """终态节点：基于全部来源流式生成最终回答。

        复用 st.messages（已含 system / history / 多模态图片），
        不再用 _build_final_prompt 重建——否则会丢失 image_url content blocks
        和会话历史上下文。
        """
        # 基于 st.messages 追加「来源 + 回答指令」，不丢弃已有消息
        final_messages = list(st.messages)  # 浅拷贝：system + history + user(含图)
        # 按「引用来源数」上限裁剪（ModelConfig 的 sourceCount），保证最终引用条数受控；
        # 重新发射 sources 事件，前端用最终裁剪后的列表替换展示
        if self._source_count and len(st.all_sources) > self._source_count:
            st.all_sources = st.all_sources[: self._source_count]
            # all_sources 已是格式化 dict，不能再过 _format_sources（键为
            # camelCase，二次格式化会 KeyError）；直接发快照
            yield {"event": "sources", "data": list(st.all_sources)}
        if st.all_sources:
            ctx = self._sources_to_context(st.all_sources, st.source_content)
            if st.graph_reasoning:
                # 8.5：把图谱多跳推理链路作为独立段落拼进上下文，
                # 让 LLM 在生成时能显式引用实体间关系（"据图谱，A 经由 B 影响 C"）。
                ctx += "\n\n【知识图谱推理链路】\n" + st.graph_reasoning
            final_messages.append({
                "role": "user",
                "content": (
                    f"来源资料：\n{ctx}\n\n"
                    "请基于以上对话上下文及来源资料回答用户问题。"
                    "引用时使用 [1] [2] 标注编号；若某条标记为联网来源可注明「据联网信息」；"
                    "确实无来源覆盖时再如实说明。"
                    "\n【排版】保持版面清爽：短答案用连贯语句，不必列点；"
                    "仅在要点较多时用单层列表，避免多级嵌套与堆砌标题；"
                    "加粗只留给关键术语，不要大段加粗；不要使用 emoji。"
                    + self._concise_suffix()
                ),
            })
        else:
            # 检索已执行但无结果 → 明确禁止编造
            final_messages.append({
                "role": "user",
                "content": (
                    "注意：已在知识库中检索，但未找到与问题相关的文档。\n"
                    "请直接告知用户「当前知识库中没有找到相关内容」，不要编造或猜测具体信息。"
                    "如果用户的问题属于常识范畴可以简短回答，否则建议缩小范围重新提问。"
                ) + self._concise_suffix(),
            })
        full_answer = ""
        gen_args: dict = {"model": self._model_override}
        if self._gen_temperature is not None:
            gen_args["temperature"] = self._gen_temperature
        if self._gen_top_p is not None:
            gen_args["top_p"] = self._gen_top_p
        if self._gen_max_tokens is not None:
            gen_args["max_tokens"] = self._gen_max_tokens
        async for delta in self.llm.stream_chat(final_messages, **gen_args):
            full_answer += delta
            yield {"event": "delta", "data": {"content": delta}}
        st.final_answer_text = full_answer
        st.next = "__end__"

    async def _n_finish(self, st: "_AgentState") -> AsyncIterator[dict]:
        """终态节点：direct_answer 的收尾（候选内容 / 改走生成 / 纯通用回答）。"""
        if st.candidate:
            st.final_answer_text = st.candidate
            yield {"event": "delta", "data": {"content": st.candidate}}
        elif st.all_sources:
            # 有检索结果但 LLM 选了 direct_answer（无内容）→ 改走生成，避免丢来源
            st.next = "_n_generate"
            return
        else:
            # 无任何检索结果时基于 st.messages 回答（保留多模态图片 + 历史）
            quick_msgs = [
                {"role": "system", "content": (
                    "你是「知海 Knoa」，一个企业级知识助手，面向公司各部门（如跨境电商、财务、产品、实施等）提供知识问答。"
                    "请简洁友好地回答用户的问题。不要自我介绍或罗列功能。"
                ) + self._memory_section() + self._summary_section()},
                *list(st.messages)[1:],  # 跳过 system，保留 history + user(含图)
            ]
            try:
                st.final_answer_text = await self.llm.chat(
                    quick_msgs, model=self._model_override,
                    temperature=self._gen_temperature, top_p=self._gen_top_p,
                    max_tokens=self._gen_max_tokens,
                )
            except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, fallback friendly reply if final chat fails)
                st.final_answer_text = "好的，收到！"
            yield {"event": "delta", "data": {"content": st.final_answer_text}}
        st.next = "__end__"

    async def _n_start_skip(self, st: "_AgentState") -> AsyncIterator[dict]:
        """入口节点：问候/常识类问题，跳过检索直接友好回答。"""
        yield {
            "event": "thinking",
            "data": {"step": 0, "action": "direct_answer",
                     "detail": "识别为常识/实时问题，跳过检索直接回答", "raw_reasoning": ""},
        }
        # 用户消息：结构性防御——优先复用 st.messages 里已拼好的多模态内容
        # （含图片 image_url blocks）。即便理论上带图走 _n_route 不会到这，
        # 这里也不依赖入口守卫，任何重构都不会再掉图。纯文本时退化为 st.question。
        user_turn = next(
            (m for m in reversed(st.messages) if m.get("role") == "user"), None
        )
        user_content = user_turn["content"] if user_turn else st.question
        quick_messages = [
            {"role": "system", "content": (
                "你是「知海 Knoa」，一个企业级知识助手，面向公司各部门（如跨境电商、财务、产品、实施等）提供知识问答。"
                "用户问了一个知识库无法覆盖的常识/实时类问题（如天气、时间、股价等），"
                "请友好简洁地回答。如果确实不知道，就直说。不要自我介绍或罗列功能。"
            ) + self._memory_section()},
            {"role": "user", "content": user_content},
        ]
        full_answer = ""
        async for delta in self.llm.stream_chat(
            quick_messages, model=self._model_override,
            temperature=self._gen_temperature, top_p=self._gen_top_p,
            max_tokens=self._gen_max_tokens,
        ):
            full_answer += delta
            yield {"event": "delta", "data": {"content": delta}}
        st.final_answer_text = full_answer
        st.next = "__end__"

    async def _n_start_simple(self, st: "_AgentState") -> AsyncIterator[dict]:
        """入口节点：simple 意图快路。跳过 route LLM 决策，直接检索。

        检索词来自意图分类时零成本改写的 query（已预置在 route_result）；
        发一条固定 thinking 事件保证前端决策链展示不断，随后直奔 _n_retrieve。
        省掉原本 route 的完整 tool_call 往返（system+tools+历史），simple
        问题首 token 明显变快。
        """
        st.step += 1
        q = (st.route_result.arguments.get("query") if st.route_result else "") or st.question
        yield {
            "event": "thinking",
            "data": {"step": st.step, "action": "retrieve",
                     "detail": f"简单问题快路：直接检索知识库「{q[:40]}」",
                     "raw_reasoning": ""},
        }
        st.next = "_n_retrieve"

    def _arm_simple_route(self, st: "_AgentState", rewritten_query: str) -> None:
        """为 simple 快路预置 route_result：_n_retrieve 天然从中取改写后的 query。

        _n_retrieve 读 route_result.arguments["query"]（缺省回退原问题），
        故只需伪造一条 retrieve 决策即可复用整条检索节点，零侵入。
        """
        st.route_result = ToolCallResult(
            name="retrieve",
            arguments={"query": (rewritten_query or "").strip() or st.question},
            raw_text="",
        )
        st.action = "retrieve"

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
                kb_id=r.get("kb_id"),
                title=r["title"], doc_id=r.get("doc_id"),
                snippet=r["snippet"],
                confidence=r.get("confidence", 0.0),
                source_type=r.get("source_type", "kb"),
                url=r.get("url"),
            ).model_dump(by_alias=True)
            for r in retrieved
        ]

    def _sources_to_context(self, retrieved: list[dict], content_by_id: "dict[int, str] | None" = None) -> str:
        """把来源拼成 LLM 上下文。优先取 content_by_id 里的 chunk 全文——
        all_sources 里的 SourceItemOut 只带 150 字 snippet，直接喂给模型
        会严重限制回答质量（尤其图谱来源，全文只在这里进入生成环节）。
        无全文时回退 content / snippet（联网来源只有 300 字摘要）。"""
        parts = []
        for r in retrieved:
            body = (content_by_id or {}).get(r["id"]) or r.get("content") or r.get("snippet", "")
            date_tag = f" [更新: {r['doc_updated_at']}]" if r.get("doc_updated_at") else ""
            parts.append(f"\n[{r['id']}] {r['title']} ({r['kb']}){date_tag}\n{body}")
        return "\n".join(parts)

    @staticmethod
    def _extract_citations(text: str) -> list[int]:
        return sorted(set(int(m) for m in re.findall(r"\[(\d+)\]", text)))

    def _build_system_prompt(self) -> str:
        """路由 system prompt = 默认路由器指令 + 记忆 + 摘要 + 用户自定义人设。"""
        prompt = AGENT_SYSTEM_PROMPT + self._memory_section() + self._summary_section()
        if self._custom_system_prompt and self._custom_system_prompt.strip():
            prompt += (
                "\n\n## 用户自定义补充指令（优先遵循，但不覆盖以上核心原则）\n"
                + self._custom_system_prompt.strip()
            )
        return prompt

    def _concise_suffix(self) -> str:
        """简洁模式：追加到最终生成指令的收尾约束（不开启则空串）。"""
        if self._concise_mode:
            return "\n\n【回答风格】请尽量简洁，直接给结论和要点，去掉寒暄、铺垫和重复解释。"
        return ""

    def _memory_section(self) -> str:
        """把召回的用户记忆格式化成可注入 system prompt 的文本块（无记忆则返回空串）。"""
        if not self._memories:
            return ""
        lines = ["\n\n## 用户长期记忆（来自历史对话，不与该用户显式意愿冲突时请优先遵循）"]
        for m in self._memories:
            lines.append(f"- {m}")
        return "\n".join(lines)

    def _summary_section(self) -> str:
        """把滚动摘要格式化成可注入 system prompt 的文本块（无摘要则返回空串）。"""
        if not getattr(self, "_summary_text", ""):
            return ""
        return (
            "\n\n## 对话历史摘要（较早对话已压缩，供你理解上下文）\n"
            + self._summary_text
        )
