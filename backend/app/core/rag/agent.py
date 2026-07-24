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
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm.base import ToolCallResult
from app.core.graph import GraphStore
from app.core.memory import MemoryStore
from app.core.rag.retriever import HybridRetriever
from app.core.metrics import record_ask_trace
from app.core.rag.web_search import WebSearcher
from app.core.store.redis_store import RedisStore
from app.database import AsyncSessionLocal
from app.db import ChatMessage, ChatSession
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
- **核心原则：当用户询问知识库内的具体内容、文档信息、业务细节时，必须先调用 retrieve 检索，绝对不能直接回答。** 你不知道库里实际存了什么，直接回答一定是幻觉。
- 问题越具体/专业，越应该走检索路径
- 如果问题包含多个子问题或需要对比分析，优先做一次全面检索
- 只有在确实缺少关键信息时才触发补充检索（控制成本）
- 天气、时间日期类问题：若无知识库答案，用 web_search 联网查询实时信息，不要凭记忆编造
- 汇率/股价/最新政策/新闻等实时或易变信息：优先 web_search 联网核实
- 知识库能回答的运营/合规问题优先走 retrieve，不要无谓联网
- 回答必须简洁务实，不要自我介绍或罗列功能
- **宁可检索后说"库中未找到相关内容"，也不要不检索就直接编造答案**

## 输出格式
根据判断选择一个动作执行。如果是直接回答，就在 content 里写回复内容；
如果需要检索或联网，就调用对应的工具（retrieve / supplement_search / web_search）并填好参数。"""


# ---------------------------------------------------------------------------
# 快速预分类：明显不需要检索的问题，跳过昂贵的 LLM tool_call（省 15~40s）
# ---------------------------------------------------------------------------

_SKIP_RETRIEVAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"现在(几点|什么时间|几号|星期几|农历)", re.I),
    re.compile(r"^(现在)?(几点了?|什么时间|今天星期|今天几号)", re.I),
    re.compile(r"^[0-9]+[+\-*/][0-9]+", re.I),  # 纯数学计算（阿拉伯符号）
    re.compile(r"\d+\s*(的\s*)?(乘以|乘|×|除以|除|÷)\s*\d+|\d+\s*的\s*\d+\s*倍", re.I),  # 中文算式（125 乘以 8 / 100 的 3 倍）
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


_INTENT_PROMPT = (
    "你是跨境电商知识助手「知海 Knoa」的意图分类器。\n"
    "只输出一个英文标签，不要任何解释或标点：\n"
    "- greeting：打招呼 / 闲聊 / 常识 / 时间 / 简单寒暄（不涉及具体业务知识）\n"
    "- web_search：需要实时或易变信息（天气、股价、汇率、最新政策新闻）\n"
    "- simple：可用单篇知识库检索直接回答的具体业务问题\n"
    "- complex：需要跨实体 / 跨流程关联推理的复杂业务问题"
    "（如「A 流程和 B 流程的关系」「某政策对物流的影响」）"
)


_ROLL_SUMMARY_SYSTEM = (
    "你是一个对话摘要压缩器。给定某跨境电商运营知识助手会话里「较早的对话片段」，"
    "请把它压缩成一段简洁的摘要，供后续轮次理解上下文。\n"
    "规则：\n"
    "1. 保留关键事实：用户提到的产品/实体名称、已确认的结论、已做的决策、待办、用户偏好。\n"
    "2. 丢弃寒暄、重复、与后续无关的细节。\n"
    "3. 若给出「已有摘要」，请把新对话与已有摘要融合，输出一段连贯的新摘要（不要重复罗列）。\n"
    "4. 语言与用户一致（中文则用中文）。\n"
    "5. 输出一段紧凑的自然语言摘要，不超过 200 字。不要使用 markdown、不要解释。"
)


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


class AgenticRAGAgent:
    """Agentic RAG 代理 — 用 LLM 驱动的决策闭环替代固定检索流程。"""

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
    ):
        self.retriever = retriever
        self.llm = llm
        self.redis = redis
        self.db = db
        self.user_id = user_id
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

    async def _classify_intent(self, question: str) -> "str | None":
        """LLM 意图分类（greeting/web_search/simple/complex）。

        失败或返回空 → 返回 None，由调用方退化为正则启发式兜底。
        用流式通道拿短输出，规避推理模型非流式 content 为空的老问题。
        """
        if not self.llm:
            return None
        try:
            text = ""
            async for piece in self.llm.stream_chat(
                [
                    {"role": "system", "content": _INTENT_PROMPT},
                    {"role": "user", "content": f"问题：{question}"},
                ],
                temperature=0.0,
                max_tokens=20,
            ):
                text += piece
            text = text.strip().lower()
            for label in ("greeting", "web_search", "complex", "simple"):
                if label in text:
                    return label
            return None
        except Exception as e:
            logger.warning("intent classify failed (fallback heuristic): %s", e)
            return None

    @staticmethod
    def _heuristic_intent(question: str) -> str:
        """LLM 不可用时的兜底意图判断（保留问候/实时快路 + 关系类判 complex）。"""
        if _should_web_search(question):
            return "web_search"
        # 含关系/对比/影响类措辞 → 视为复杂业务问题，触发图谱多跳推理
        if re.search(r"(关系|区别|差异|对比|影响|联系|关联|和.{1,6}的|与.{1,6}的|vs|VS|相对于|导致|因为)", question):
            return "complex"
        return "simple"

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
            graph_reasoning_text: str = ""  # 8.5 多跳推理链路，注入 final prompt

            # ── 8.3 意图分类：LLM 判断 simple/complex/greeting/web_search ──
            # 纯 trivial（打招呼/数学/时间）直接走 greeting 快路，不浪费 LLM 调用；
            # 其余业务问题才调 LLM 分类，失败退化为正则启发式（保留问候/实时兜底）。
            intent = "simple"
            if _should_skip_retrieval(question):
                intent = "greeting"
            elif settings.INTENT_ENABLED:
                classified = await self._classify_intent(question)
                intent = classified if classified is not None else self._heuristic_intent(question)
            else:
                intent = self._heuristic_intent(question)
            use_multihop = intent == "complex"

            # ── Graph RAG：图感知检索，把实体关系相关的 chunk 也拉进来当来源 ──
            # 仅对真实业务问题生效（跳过打招呼/闲聊）；kb_id 为空（纯通用问答）也跳过。
            if self.graph and settings.GRAPH_ENABLED and kb_id and not _should_skip_retrieval(question):
                try:
                    self._graph_chunks = await self.graph.retrieve_related_chunks(
                        question, kb_id, self.db, settings.GRAPH_TOP_K
                    )
                    if self._graph_chunks:
                        # 顺序编号只给角标 [N] 用；chunk_id 必须保留 graph.py
                        # 返回的真实 DocChunk UUID，前端点「查看溯源」才能查到原文。
                        # 之前误写成 graph:{i} 合成 id，使 /api/sources 的 UUID 校验
                        # 失败（400），图谱溯源抽屉打不开 —— 这是 T1 的遗留 bug。
                        for i, g in enumerate(self._graph_chunks, len(all_sources) + 1):
                            g["id"] = i
                        all_sources.extend(self._format_sources(self._graph_chunks))
                        yield {"event": "sources", "data": self._format_sources(self._graph_chunks)}
                    # 8.5 complex 意图 → 图谱多跳推理，产出推理链路 + 追加沿途来源
                    if use_multihop:
                        chains, mh_chunks = await self.graph.multi_hop_reason(
                            question, kb_id, self.db, settings.GRAPH_MULTI_HOP_MAX
                        )
                        if chains:
                            graph_reasoning_text = "\n".join(chains)
                            yield {"event": "thinking", "data": {
                                "step": 0, "action": "graph_reason",
                                "detail": f"图谱多跳推理链路（{len(chains)} 条）",
                                "raw_reasoning": "",
                            }}
                        existing_ids = {s.get("chunk_id") for s in all_sources}
                        for c in mh_chunks:
                            if c["chunk_id"] not in existing_ids:
                                c["id"] = len(all_sources) + 1
                                all_sources.append(self._format_sources([c])[0])
                                existing_ids.add(c["chunk_id"])
                        if mh_chunks:
                            yield {"event": "sources", "data": self._format_sources(mh_chunks)}
                except Exception as e:
                    logger.warning("graph retrieve/multihop failed (skip inject): %s", e)

            # ── 构造共享状态 + 选择入口节点（LangGraph 的 start 边）──
            # 多模态:把文本 + 图片拼成 OpenAI 多模态 content blocks
            # (纯文本 → str;带图 → list)。agent 决策(tool_call)也能看到图。
            user_content = self._build_user_content(question, files)
            st = _AgentState(question, kb_id)
            st.all_sources = all_sources
            st.intent = intent
            st.use_multihop = use_multihop
            st.graph_reasoning = graph_reasoning_text

            # ── 加载会话历史 + 滚动摘要，注入上下文 ──
            raw_history, summary = await self._load_session_history(session)
            self._summary_text = summary or ""
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
                    # 用户关闭联网 → 退化为普通业务路由，走知识库检索
                    intent = "simple"
                    st.next = "_n_route"
                else:
                    st.web_loop = False
                    st.next = "_n_web_search"      # 实时信息 → 搜一次即生成
            else:
                st.next = "_n_route"               # simple/complex 业务问题 → agent 决策循环

            # ── 跑图：按 st.next 派发节点，直到 __end__ ──
            async for ev in self._run_agent_loop(st):
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

        except Exception as e:
            record_ask_trace(
                latency=time.perf_counter() - t0,
                retrieved=retrieved,
                graph_used=graph_used,
                intent=intent,
                model=self._model_override or settings.LLM_MODEL,
                tokens_est=0,
                is_error=True,
            )
            yield {"event": "error", "data": {"message": str(e)}}

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
                _should_skip_retrieval(st.question)
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
        else:
            st.next = "_n_generate"

        # 步数上限：达到 MAX_STEPS 仍选了检索类动作 → 强制生成，保证终止
        if st.step >= self.MAX_STEPS and st.next in ("_n_retrieve", "_n_supplement", "_n_web_search"):
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
        if retrieved:
            # 连续编号，接在已有来源（图/联网预检索）之后，
            # 避免与图谱预检索已占用的 1..N 撞号导致引用错位
            for i, r in enumerate(retrieved, len(st.all_sources) + 1):
                r["id"] = i
            sources = self._format_sources(retrieved)
            st.all_sources.extend(sources)
            yield {"event": "sources", "data": sources}
            context_text = self._sources_to_context(retrieved)
            st.messages.append({"role": "assistant", "content": f"[已调用检索 retrieve，针对「{query}」检索到 {len(retrieved)} 条相关文档]"})
            st.messages.append({"role": "user", "content": f"检索结果：\n{context_text}\n\n基于以上信息，请直接给出最终回答。如果信息明显不足，才调用 supplement_search（大多数情况下直接回答即可）。"})
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
        if retrieved:
            # 同 _n_retrieve：连续编号，避免与图谱预检索的 1..N 撞号
            for i, r in enumerate(retrieved, len(st.all_sources) + 1):
                r["id"] = i
            sources = self._format_sources(retrieved)
            st.all_sources.extend(sources)
            yield {"event": "sources", "data": sources}
            context_text = self._sources_to_context(retrieved)
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
        # 与启发式直搜（_should_web_search 直接进本节点，route_result 为 None，退用原问题）
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
            st.all_sources.extend(web)
            yield {"event": "sources", "data": self._format_sources(web)}
            context_text = self._sources_to_context(web)
            st.messages.append({"role": "assistant", "content": f"[已调用联网搜索 web_search，针对「{query}」检索到 {len(web)} 条网络结果]"})
            st.messages.append({"role": "user", "content": f"联网搜索结果：\n{context_text}\n\n结合以上信息（含知识库与联网结果），请直接给出最终回答。"})
        else:
            st.messages.append({"role": "assistant", "content": "[联网搜索未找到相关结果]"})
            st.messages.append({"role": "user", "content": "联网搜索无结果。请基于已有信息尽量回答。"})
        # 启发式直搜路径（web_loop=False）搜完即生成；agent 循环内则回到 route 再决策
        st.next = "_n_route" if st.web_loop else "_n_generate"

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
            yield {"event": "sources", "data": self._format_sources(st.all_sources)}
        if st.all_sources:
            ctx = self._sources_to_context(st.all_sources)
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
                    "你是「知海 Knoa」，一个跨境电商运营知识助手。"
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
            except Exception:
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
                "你是「知海 Knoa」，一个跨境电商运营知识助手。"
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

    def _sources_to_context(self, retrieved: list[dict]) -> str:
        parts = []
        for r in retrieved:
            body = r.get("content") or r.get("snippet", "")
            parts.append(f"\n[{r['id']}] {r['title']} ({r['kb']})\n{body}")
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

    async def _load_session_history(self, session) -> "tuple[list[dict], str | None]":
        """返回 (保留区原始消息, 滚动摘要文本)。

        保留最近 CONV_SUMMARY_KEEP_RECENT 条原始消息（细节不失真），
        更早的已由后台 _roll_summary 压缩进 session.summary（长会话上下文）。
        summary 取自 ChatSession.summary（由 _roll_summary 异步维护）。
        排除当前轮刚 flush 的 user 消息。
        """
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.asc())
        )
        all_msgs = result.scalars().all()

        # 排除最后一条（本轮刚 flush 的 user message）；首条消息则无历史
        if len(all_msgs) > 1:
            all_msgs = all_msgs[:-1]
        else:
            return [], (session.summary or None)

        n = len(all_msgs)
        keep = settings.CONV_SUMMARY_KEEP_RECENT
        if n <= keep:
            # 全部作原始消息；若 session 已有旧摘要也一并带上
            return self._msgs_to_llm(all_msgs), (session.summary or None)

        recent = all_msgs[-keep:]
        return self._msgs_to_llm(recent), (session.summary or None)

    def _msgs_to_llm(self, msgs) -> list[dict]:
        """把 ChatMessage 列表回构为 LLM messages（多模态 user 回构 content blocks）。"""
        history: list[dict] = []
        for msg in msgs:
            if msg.role == "user":
                if msg.attachments:
                    content = self._build_user_content(msg.content or "", msg.attachments)
                else:
                    content = msg.content or ""
                history.append({"role": "user", "content": content})
            elif msg.role == "assistant":
                if msg.content:
                    history.append({"role": "assistant", "content": msg.content})
        return history

    @staticmethod
    def _format_history_text(msgs) -> str:
        """把一段历史消息拼成纯文本（给 LLM 做摘要用）。

        多模态图片：只标注「附 N 张图片」，绝不塞 base64（太大且无意义）。
        """
        parts = []
        for m in msgs:
            if m.role == "user":
                extra = ""
                if m.attachments:
                    n = len(m.attachments) if isinstance(m.attachments, list) else 0
                    if n:
                        extra = f"（附 {n} 张图片）"
                parts.append(f"用户：{(m.content or '').strip()}{extra}")
            elif m.role == "assistant" and m.content:
                parts.append(f"助手：{m.content.strip()}")
        return "\n".join(parts)

    def _summary_section(self) -> str:
        """把滚动摘要格式化成可注入 system prompt 的文本块（无摘要则返回空串）。"""
        if not getattr(self, "_summary_text", ""):
            return ""
        return (
            "\n\n## 对话历史摘要（较早对话已压缩，供你理解上下文）\n"
            + self._summary_text
        )

    async def _roll_summary(self, session_id: uuid.UUID) -> None:
        """后台滚动摘要：把窗口外的旧对话段压缩进 ChatSession.summary。

        与 Mem0 的 _save_memory 同源模式——自己开独立 db session，
        不阻塞已返回的 SSE 流；本轮 user+assistant 落库后才触发，
        故能读到完整历史。下一轮提问时 summary 才被注入
        （滚动摘要本就是给未来轮次用的）。

        触发闸门（省成本）：
        - 历史总条数 <= KEEP_RECENT：不摘要
        - 窗口外、尚未摘要的段为空：跳过
        - 非首次且累计新段 < STEP：跳过（每积累 STEP 条才重摘一次）
        """
        if not settings.CONV_SUMMARY_ENABLED:
            return
        try:
            async with AsyncSessionLocal() as s:
                sess = (
                    await s.execute(
                        select(ChatSession).where(ChatSession.id == session_id)
                    )
                ).scalar_one_or_none()
                if not sess:
                    return
                msgs = (
                    await s.execute(
                        select(ChatMessage)
                        .where(ChatMessage.session_id == session_id)
                        .order_by(ChatMessage.created_at.asc())
                    )
                ).scalars().all()

                n = len(msgs)
                keep = settings.CONV_SUMMARY_KEEP_RECENT
                if n <= keep:
                    return  # 还不够长，无需摘要

                window_start = n - keep  # 窗口外（需摘要）/ 窗口内（保留）分界
                already = sess.summarized_count or 0
                if window_start <= already:
                    return  # 没有新窗口外消息需要摘要
                new_segment_count = window_start - already
                if already > 0 and new_segment_count < settings.CONV_SUMMARY_STEP:
                    return  # 非首次：累计新段未达 STEP，先不重摘（省 LLM 调用）

                segment_text = self._format_history_text(msgs[already:window_start])
                if not segment_text.strip():
                    # 边界前移，避免反复空尝试
                    sess.summarized_count = window_start
                    await s.commit()
                    return

                prompt = [
                    {"role": "system", "content": _ROLL_SUMMARY_SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"[已有摘要]\n{sess.summary or '（无）'}\n\n"
                            f"[本轮需要压缩的新对话]\n{segment_text}"
                        ),
                    },
                ]
                try:
                    new_summary = (await self.llm.chat(prompt, temperature=0.2)).strip()
                except Exception as e:
                    logger.warning("roll summary llm failed (skip): %s", e)
                    return
                if not new_summary:
                    sess.summarized_count = window_start
                    await s.commit()
                    return

                sess.summary = new_summary
                sess.summarized_count = window_start
                await s.commit()
        except Exception as e:
            logger.warning("roll summary failed (skipped): %s", e)

    @staticmethod
    def _build_user_content(question: str, files: "list[dict] | None") -> "str | list[dict]":
        """把文本 + 多模态文件拼成 OpenAI 多模态 content。

        纯文本问题 → 返回 str;带图 → 返回 content blocks list
        （text + image_url/data URI）。当前模型仅支持 image，故 audio/video
        不拼进 LLM 消息（仅作为附件入库/回显），这里只处理 image。
        """
        if not files:
            return question
        blocks: list[dict] = []
        if question.strip():
            blocks.append({"type": "text", "text": question})
        for f in files:
            if f.get("kind") == "image":
                # OSS 直传优先用 url（大模型直接拉取，省去大 base64 往返）；
                # 否则回退旧 data URI 路径
                if f.get("url"):
                    blocks.append({
                        "type": "image_url",
                        "image_url": {"url": f["url"]},
                    })
                elif f.get("data_b64"):
                    blocks.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{f['mime_type']};base64,{f['data_b64']}"},
                    })
        return blocks if blocks else question

    async def _get_or_create_session(self, session_id: str | None, question: str) -> ChatSession:
        if session_id:
            # 前端传入的 session_id 可能非合法 UUID，先校验再查库，
            # 否则 uuid.UUID() 抛 ValueError → 被顶层兜底成 500，应明确 400。
            try:
                sid = uuid.UUID(session_id)
            except (ValueError, AttributeError, TypeError):
                raise HTTPException(status_code=400, detail="无效的会话 ID")
            result = await self.db.execute(select(ChatSession).where(ChatSession.id == sid))
            s = result.scalar_one_or_none()
            if s:
                return s
        # 隐式建会话（主聊天里直接提问、未指定 session_id 时）必须绑定
        # user_id，否则 list_sessions 按 user_id 过滤会把该会话排除，
        # 导致「回复能显示、sessionId 也返回了，却在历史列表里找不到」。
        s = ChatSession(title=question[:50], user_id=self.user_id)
        self.db.add(s)
        await self.db.flush()
        return s
