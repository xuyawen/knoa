import json

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.llm.openai_compat import OpenAICompatProvider
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.pipeline import RAGPipeline
from app.core.rag.es_client import ESClient
from app.core.rag.es_retriever import ESRetriever
from app.core.rag.retriever import HybridRetriever
from app.core.security import get_current_user, get_kb_permission_level
from app.core.store.redis_store import RedisStore
from app.config import settings
from app.db import User
from app.deps import get_db, get_embedder, get_llm, get_redis
from app.models.chat import AskRequest

router = APIRouter()


@router.post("/ask")
async def ask(
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
    embedder: EmbeddingModel = Depends(get_embedder),
    llm: OpenAICompatProvider = Depends(get_llm),
    redis: RedisStore = Depends(get_redis),
    user: User = Depends(get_current_user),
):
    # 库级权限：问答目标 KB 必须对该用户可见
    if req.knowledge_base:
        level = await get_kb_permission_level(db, req.knowledge_base, user)
        if level is None:
            raise HTTPException(status_code=403, detail="无权访问该知识库")

    # 检索器选择：ES 可用且目标库已建索引 → ES 混合检索；
    # 否则回退 pgvector HybridRetriever（ES 未启用 / 索引不存在 / 网络异常都安全降级）
    es = ESClient()
    if es.enabled and req.knowledge_base and await es.index_exists(req.knowledge_base):
        retriever = ESRetriever(embedder, es, settings.RRF_K)
    else:
        retriever = HybridRetriever(embedder, db, settings.RRF_K)
    pipeline = RAGPipeline(retriever, llm, redis, db)

    async def event_generator():
        async for event in pipeline.stream_answer(
            question=req.question,
            kb_id=req.knowledge_base,
            session_id=req.session_id,
        ):
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"], ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())
