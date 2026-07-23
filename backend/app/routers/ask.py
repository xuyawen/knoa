import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.core.llm.openai_compat import OpenAICompatProvider
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.pipeline import RAGPipeline
from app.core.rag.es_retriever import ESRetriever
from app.core.rag.retriever import HybridRetriever
from app.core.security import (
    get_accessible_kb_ids,
    get_current_user,
    get_kb_permission_level,
)
from app.core.store.redis_store import RedisStore
from app.config import settings
from app.db import User
from app.database import AsyncSessionLocal
from app.deps import get_embedder, get_llm, get_redis, get_es
from app.models.chat import AskRequest
from app.models.operation_log import record_operation

router = APIRouter()
logger = logging.getLogger("knoa.ask")


@router.post("/ask")
async def ask(
    req: AskRequest,
    request: Request,
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
    # 多模态能力：当前模型仅确认支持 image。不支持的模态（audio/video）不拦截——
    # 仍作为附件入库/回显（用户记录留痕），但 agent 构造 LLM 消息时只会把 image
    # 拼成 image_url block，audio/video 不被喂给模型（避免无谓报错）。
    unsupported = [f.kind for f in req.files if not settings.MODEL_CAPABILITIES.get(f.kind, False)]
    if unsupported:
        logger.info("chat attachments with unsupported modality (stored, not sent to model): %s", unsupported)

    # 库级权限：问答目标 KB 必须对该用户可见。
    # 用一次性 DB 会话完成（流式开始前），不占用流式生成器的会话生命周期 ——
    # 否则请求返回时 get_db 的 finally 会把还在用的会话关掉，造成事务回滚 /
    # 会话丢失（表现为「刚问的对话从历史里凭空消失」）。
    async with AsyncSessionLocal() as perm_db:
        accessible_kb_ids: "list[str] | None" = None
        if req.knowledge_base:
            level = await get_kb_permission_level(perm_db, req.knowledge_base, user)
            if level is None:
                raise HTTPException(status_code=403, detail="无权访问该知识库")
        else:
            # 未指定 KB：将检索范围严格限定为用户有权访问的 KB 列表，
            # 防止已登录用户跨库检索其无权查看的知识库内容（P0-2）。
            accessible_kb_ids = await get_accessible_kb_ids(perm_db, user)
            if not accessible_kb_ids:
                raise HTTPException(status_code=403, detail="无权访问任何知识库")

    async def event_generator():
        logger.info("ask stream start", extra={"request_id": rid})
        n = 0
        # 流式生成器自己持有 DB 会话，并在生成结束后才关闭 ——
        # 这样事务生命周期跟随 SSE 流，而非跟随「路由返回」（sse-starlette
        # 在后台 task 跑生成器，路由早已 return，get_db 的 finally 会提前关会话，
        # 导致会话/消息未提交就被回滚，表现为「刚问的对话从历史里凭空消失」）。
        gen_db = AsyncSessionLocal()
        try:
            # 埋点：每条问答（无论中途断开）都记一条 operation_log，
            # 作为 Dashboard「AI 问答 / 用户搜索」与趋势图真实数据源。
            # 搜索页复用本接口时传 mode='search'，埋点动作相应区分，
            # 使「问答次数」与「搜索次数」成为两条独立真实数据。
            await record_operation(
                gen_db,
                user,
                "search" if req.mode == "search" else "ask",
                detail=req.question[:200],
            )
            es = get_es()
            if es.enabled and req.knowledge_base and await es.index_exists(req.knowledge_base):
                retriever = ESRetriever(embedder, es, settings.RRF_K)
            else:
                # 未指定 KB 时，注入可访问范围做库级隔离过滤
                retriever = HybridRetriever(
                    embedder, gen_db, settings.RRF_K, kb_ids=accessible_kb_ids
                )
            pipeline = RAGPipeline(
                retriever, llm, redis, gen_db,
                user_id=str(user.id),
                embedder=embedder,
            )

            async for event in pipeline.stream_answer(
                question=req.question,
                kb_id=req.knowledge_base,
                session_id=req.session_id,
                files=[f.model_dump(by_alias=False) for f in req.files] or None,
                model=user.preferred_model,
            ):
                # 客户端断开（用户点了「停止」）→ 优雅退出，不再继续烧 LLM 算力
                if await request.is_disconnected():
                    logger.info("ask stream client disconnected, stop early", extra={"request_id": rid})
                    break
                n += 1
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"], ensure_ascii=False),
                }
        finally:
            await gen_db.close()
        logger.info("ask stream done events=%d", n, extra={"request_id": rid})

    return EventSourceResponse(event_generator())
