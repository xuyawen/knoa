from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm.base import LLMConfig
from app.core.llm.openai_compat import OpenAICompatProvider
from app.core.rag.embeddings import EmbeddingModel
from app.core.store.redis_store import RedisStore
from app.database import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


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
