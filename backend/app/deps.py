from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import model_supports_vision, settings, vision_llm_available
from app.core.llm.base import LLMConfig
from app.core.llm.openai_compat import OpenAICompatProvider
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.es_client import ESClient
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
def get_vision_llm() -> "OpenAICompatProvider | None":
    """视觉模型 provider（阿里云百炼）；未配置 key 返回 None，由调用方降级。

    key 留空时复用 EMBEDDING_API_KEY（同为百炼 DashScope key）。
    """
    if not vision_llm_available():
        return None
    return OpenAICompatProvider(LLMConfig(
        base_url=settings.VISION_LLM_BASE_URL,
        api_key=settings.VISION_LLM_API_KEY or settings.EMBEDDING_API_KEY,
        model=settings.VISION_LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    ))


# 主 LLM（DeepSeek）端点上额外可用的模型名（除 settings.LLM_MODEL 外）；
# 不在白名单里的模型名（如已下线的 agnes/gpt-4o）一律回落系统默认，避免 404
_MAIN_LLM_MODELS = {"deepseek-chat"}


def resolve_llm(model: "str | None", force_vision: bool = False) -> tuple[OpenAICompatProvider, "str | None"]:
    """按目标模型选 provider：视觉模型走百炼端点，其余走主 LLM（DeepSeek）。

    返回 (provider, effective_model)。force_vision=True（带图片附件）时
    强制路由视觉模型，与所选文本模型解耦。视觉模型但百炼未配置、或模型名
    已下线/未知时，降级为系统默认模型，避免把调不通的模型名打到
    错误端点报 404。
    """
    if model_supports_vision(model) or force_vision:
        vision = get_vision_llm()
        if vision is not None:
            return vision, (model if model_supports_vision(model) else None)
        return get_llm(), None
    name = (model or "").strip()
    if name and name != settings.LLM_MODEL and name not in _MAIN_LLM_MODELS:
        return get_llm(), None
    return get_llm(), model


@lru_cache
def get_redis() -> RedisStore:
    return RedisStore(settings.REDIS_URL)


@lru_cache
def get_es() -> ESClient:
    """ES 客户端单例（可选组件；内部 httpx.AsyncClient 懒创建）。

    lru_cache 保证全进程一个实例，避免每次请求 new 一个连接池且从不
    关闭导致连接泄漏（P1-1）。进程退出由 main.lifespan 统一 aclose。
    """
    return ESClient()
