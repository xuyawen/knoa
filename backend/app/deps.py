from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm.base import LLMConfig
from app.core.llm.openai_compat import OpenAICompatProvider
from app.core.rag.embeddings import EmbeddingModel
from app.core.store.redis_store import RedisStore
from app.database import AsyncSessionLocal


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """每个 HTTP 请求一个 DB 会话（请求级单例）。

    同一次请求里所有依赖（鉴权取 user、建库时写 knowledge_base
    + kb_permission）共享同一个 session / 同一条连接，从而保证
    「同一事务内多表写入」落在同一连接（外键彼此可见）。
    请求结束统一关闭会话。这是 FastAPI 推荐的请求级会话模式，
    也顺带规避了「多个 Depends(get_db) 各自 checkout 一条连接」
    导致的跨连接事务问题。
    """
    db = getattr(request.state, "db", None)
    if db is None:
        db = AsyncSessionLocal()
        request.state.db = db
    try:
        yield db
    finally:
        await db.close()


@lru_cache
def get_embedder() -> EmbeddingModel:
    return EmbeddingModel(settings.EMBEDDING_MODEL)


@lru_cache
def get_llm() -> OpenAICompatProvider:
    return OpenAICompatProvider(LLMConfig(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    ))


@lru_cache
def get_redis() -> RedisStore:
    return RedisStore(settings.REDIS_URL)
