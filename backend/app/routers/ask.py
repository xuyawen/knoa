import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
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
logger = logging.getLogger("knoa.ask")


@router.post("/ask")
async def ask(
    req: AskRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    embedder: EmbeddingModel = Depends(get_embedder),
    llm: OpenAICompatProvider = Depends(get_llm),
    redis: RedisStore = Depends(get_redis),
    user: User = Depends(get_current_user),
):
    # 显式取 rid（sse-starlette 在独立 task 跑生成器，contextvars 可能不传播）
    rid = getattr(request.state, "request_id", "-")
    logger.info(
        "ask recv kb=%s q=%s files=%d",
        req.knowledge_base, req.question[:80], len(req.files),
        extra={"request_id": rid},
    )
    # 多模态能力校验：当前模型不支持的模态（audio/video）直接 400 中文报错
    for f in req.files:
        if not settings.MODEL_CAPABILITIES.get(f.kind, False):
            kind_cn = {"audio": "音频", "video": "视频", "image": "图片"}.get(f.kind, f.kind)
            raise HTTPException(
                status_code=400,
                detail=f"当前模型暂不支持{kind_cn}输入，请移除后重试（仅支持图片）",
            )

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
    pipeline = RAGPipeline(
        retriever, llm, redis, db,
        user_id=str(user.id),
        embedder=embedder,
    )

    async def event_generator():
        logger.info("ask stream start", extra={"request_id": rid})
        n = 0
        async for event in pipeline.stream_answer(
            question=req.question,
            kb_id=req.knowledge_base,
            session_id=req.session_id,
            files=[f.model_dump(by_alias=False) for f in req.files] or None,
        ):
            n += 1
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"], ensure_ascii=False),
            }
        logger.info("ask stream done events=%d", n, extra={"request_id": rid})

    return EventSourceResponse(event_generator())
