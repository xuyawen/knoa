import base64
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
    ScopeContext,
    compute_visible_dept_ids,
    get_accessible_kb_ids,
    get_current_user,
    get_kb_permission_level,
    is_super_admin,
    require_permission,
)
from app.core.rbac import Perm
from app.core.ratelimit import rate_limit
from app.core.store.redis_store import RedisStore
from app.core.rag.parsers import UnsupportedFormatError, parse_document
from app.config import model_supports_vision, settings
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
    _: User = Depends(require_permission(Perm.AI_QA)),
    _rl: None = Depends(rate_limit(10, 60, "ask")),  # 每用户 60s 内最多 10 次问答
):
    # 显式取 rid（sse-starlette 在独立 task 跑生成器，contextvars 可能不传播）
    rid = getattr(request.state, "request_id", "-")
    logger.info(
        "ask recv kb=%s q=%s files=%d",
        req.knowledge_base, req.question[:80], len(req.files),
        extra={"request_id": rid},
    )
    # 附件按模型能力分流（前端已做同款 gating，此处为兜底，保证任何模型都不报错）：
    # - image：仅视觉模型保留（拼 image_url）；文本模型（如 DeepSeek）静默丢弃；
    # - document：解析提取文本注入上下文，全模型可用；解析失败静默跳过；
    # - audio/video：无模型/管道支持，前端已移除，后端静默忽略。
    vision = model_supports_vision(req.model or user.preferred_model)
    processed_files: list[dict] = []
    for f in req.files:
        if f.kind == "image":
            if vision:
                processed_files.append(f.model_dump(by_alias=False))
        elif f.kind == "document" and f.data_b64:
            try:
                raw = base64.b64decode(f.data_b64)
                parsed = parse_document(f.name or "document", raw)
                processed_files.append({
                    "kind": "document",
                    "name": f.name,
                    "text": parsed.text[: settings.CHAT_DOC_MAX_CHARS],
                })
            except (UnsupportedFormatError, ValueError) as e:
                logger.info("chat document parse skipped: %s", e)
    if len(processed_files) != len(req.files):
        logger.info(
            "ask attachments filtered vision=%s kept=%d/%d",
            vision, len(processed_files), len(req.files),
            extra={"request_id": rid},
        )

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
            # scope 补全：该库 admin（含超管隐式 admin）可见库内全部文档（含他人 private）
            scope_is_admin = level == "admin"
        else:
            # 未指定 KB：将检索范围严格限定为用户有权访问的 KB 列表，
            # 防止已登录用户跨库检索其无权查看的知识库内容（P0-2）。
            accessible_kb_ids = await get_accessible_kb_ids(perm_db, user)
            if not accessible_kb_ids:
                raise HTTPException(status_code=403, detail="无权访问任何知识库")
            # 全部知识库模式：仅超管豁免 scope 过滤
            scope_is_admin = await is_super_admin(perm_db, user)
        # 部门可见子树：非 admin 才需计算（admin 跳过 scope 过滤）
        visible_dept_ids = frozenset()
        if not scope_is_admin:
            visible_dept_ids = await compute_visible_dept_ids(perm_db, user)
    # 文档级可见性上下文：注入检索器，private 仅本人、department 命中可见部门子树
    scope_ctx = ScopeContext(
        user_id=str(user.id), is_admin=scope_is_admin, visible_dept_ids=visible_dept_ids
    )

    async def event_generator():
        logger.info("ask stream start", extra={"request_id": rid})
        n = 0
        src_count = 0
        logged = None
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
            logged = await record_operation(
                gen_db,
                user,
                "search" if req.mode == "search" else "ask",
                detail=req.question[:200],
            )
            es = get_es()
            retriever = None
            if es.enabled:
                if req.knowledge_base and await es.index_exists(req.knowledge_base):
                    # 指定单库且索引已建 → ES 快路（kNN+BM25，免内存全量余弦）
                    retriever = ESRetriever(embedder, es, settings.RRF_K, scope_ctx=scope_ctx)
                elif accessible_kb_ids:
                    # 「全部知识库」模式：ES 跨索引检索用户可访问的全部库，
                    # 避免把全量 chunk 拉进内存算余弦（库多量大时是主要瓶颈）
                    retriever = ESRetriever(
                        embedder, es, settings.RRF_K,
                        fallback_kb_ids=[str(k) for k in accessible_kb_ids],
                        scope_ctx=scope_ctx,
                    )
            if retriever is None:
                # ES 不可用 / 索引未建：回退 pgvector 内存混合检索，
                # 未指定 KB 时注入可访问范围做库级隔离过滤
                retriever = HybridRetriever(
                    embedder, gen_db, settings.RRF_K, kb_ids=accessible_kb_ids,
                    scope_ctx=scope_ctx,
                )
            pipeline = RAGPipeline(
                retriever, llm, redis, gen_db,
                user_id=str(user.id),
                embedder=embedder,
                dept_id=str(user.department_id) if user.department_id else None,
                accessible_kb_ids=accessible_kb_ids,
            )

            async for event in pipeline.stream_answer(
                question=req.question,
                kb_id=req.knowledge_base,
                session_id=req.session_id,
                files=processed_files or None,
                model=req.model or user.preferred_model,
                temperature=req.temperature,
                top_p=req.top_p,
                top_k=req.top_k,
                web_search=req.web_search,
                system_prompt=req.system_prompt,
                concise_mode=req.concise_mode,
                max_tokens=req.max_tokens,
                source_count=req.source_count,
                web_provider=req.web_provider,
            ):
                # 客户端断开（用户点了「停止」）→ 优雅退出，不再继续烧 LLM 算力
                if await request.is_disconnected():
                    logger.info("ask stream client disconnected, stop early", extra={"request_id": rid})
                    break
                # 捕获检索来源数量，问答结束后回填到操作日志（知识缺口榜数据源）
                if event.get("event") == "sources":
                    data = event.get("data")
                    if isinstance(data, dict):
                        items = data.get("items") or data.get("sources") or []
                    else:
                        items = data or []
                    src_count = len(items)
                n += 1
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"], ensure_ascii=False),
                }
        finally:
            # 回填检索命中数（best-effort，失败不影响主流程）
            if logged is not None:
                try:
                    logged.source_count = src_count
                    await gen_db.commit()
                except Exception as e:  # noqa: BLE001
                    logger.warning("ask backfill source_count failed: %s", e)
            await gen_db.close()
        logger.info("ask stream done events=%d src=%d", n, src_count, extra={"request_id": rid})

    return EventSourceResponse(event_generator())
