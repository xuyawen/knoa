import json

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.llm.openai_compat import OpenAICompatProvider
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.pipeline import RAGPipeline
from app.core.rag.retriever import HybridRetriever
from app.core.store.redis_store import RedisStore
from app.config import settings
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
):
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
