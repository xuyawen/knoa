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
from app.core.rag.retriever import HybridRetriever
from app.core.store.redis_store import RedisStore
from app.db import ChatSession
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
        max_steps: int = 3,
    ):
        self._agent = AgenticRAGAgent(retriever, llm, redis, db)
        self._agent.MAX_STEPS = max_steps

    async def stream_answer(
        self,
        question: str,
        kb_id: str | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[dict]:
        """流式回答 — 事件格式与前端 SSE 消费端兼容。

        Events:
          thinking   — Agent 决策步骤（新增，前端可选渲染）
          sources    — 知识库来源片段列表
          delta      — 流式回答文本片段
          done       — 完成（含 messageId / citations / sessionId）
          error      — 错误信息
        """
        async for event in self._agent.stream_answer(question, kb_id, session_id):
            yield event
