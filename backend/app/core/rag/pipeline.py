"""RAG Pipeline — 对外入口，内部委托给 AgenticRAGAgent。

这个模块保留是为了：
1. 保持 ask router 的 import 路径不变 (app.core.rag.pipeline)
2. 作为传统 RAG → Agentic RAG 的适配层
3. 未来如果要切回传统模式（性能对比），只需改这里

实际逻辑已全部迁移到 agent.py。
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.base import LLMProvider
from app.core.rag.agent import AgenticRAGAgent
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.retriever import HybridRetriever
from app.core.store.redis_store import RedisStore
from app.config import settings


class RAGPipeline:
    """Agentic RAG Pipeline（代理到 AgenticRAGAgent）。

    接口与原版完全兼容，内部已从"固定检索-生成"升级为
    "LLM 自主决策的智能检索闭环"。
    """

    def __init__(
        self,
        retriever: HybridRetriever,
        llm: LLMProvider,
        redis: RedisStore,
        db: AsyncSession,
        user_id: str | None = None,
        embedder: "EmbeddingModel | None" = None,
        max_steps: int = 3,
    ):
        memory = None
        # 仅当开关开启 + 知道是谁 + 有向量器时才启用 Mem0；否则整个记忆链路静默跳过
        if settings.MEMORY_ENABLED and user_id and embedder:
            from app.core.memory import MemoryStore
            memory = MemoryStore(embedder)

        # 知识图谱（Phase 3 T1）：开关开启 + 有向量器时构造 GraphStore 传给 agent
        graph = None
        if settings.GRAPH_ENABLED and embedder:
            from app.core.graph import GraphStore
            graph = GraphStore(llm, embedder)

        self._agent = AgenticRAGAgent(
            retriever, llm, redis, db, user_id=user_id, memory=memory, graph=graph
        )
        self._agent.MAX_STEPS = max_steps

    async def stream_answer(
        self,
        question: str,
        kb_id: str | None = None,
        session_id: str | None = None,
        files: "list[dict] | None" = None,
        model: str | None = None,
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
        """流式回答 — 事件格式与前端 SSE 消费端兼容。

        Events:
          thinking   — Agent 决策步骤（新增，前端可选渲染）
          sources    — 知识库来源片段列表
          delta      — 流式回答文本片段
          done       — 完成（含 messageId / citations / sessionId）
          error      — 错误信息

        model: 用户偏好模型（settings.preferred_model）透传；为空用默认。
        temperature/top_p/top_k/web_search/system_prompt/concise_mode/
        max_tokens/source_count/web_provider: 前端 ModelConfig 页下发的可配置项；None=用后端默认。
        """
        async for event in self._agent.stream_answer(
            question, kb_id, session_id, files=files, model=model,
            temperature=temperature, top_p=top_p, top_k=top_k,
            web_search=web_search, system_prompt=system_prompt, concise_mode=concise_mode,
            max_tokens=max_tokens, source_count=source_count, web_provider=web_provider,
        ):
            yield event
