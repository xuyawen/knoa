import asyncio
import base64
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.graph import GraphStore
from app.core.llm.openai_compat import OpenAICompatProvider
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.es_client import ESClient
from app.core.rag.ingestor import DocumentIngester
from app.core.rag.parsers import UnsupportedFormatError, parse_document
from app.core.rag.multimodal import (
    AUDIO_EXTS,
    IMAGE_EXTS,
    VIDEO_EXTS,
    parse_multimodal,
)
from app.core.pagination import paginate
from app.core.storage import get_object_store
from app.config import settings
from app.database import AsyncSessionLocal
from app.core.security import (
    get_current_user,
    LEVEL_ORDER,
    require_kb_access,
    require_roles,
)
from app.db import DocChunk, Document, DocumentTask, KBPermission, KnowledgeBase, User
from app.deps import get_db, get_embedder, get_llm, get_es
from app.models.common import PaginatedOut
from app.models.knowledge import (
    AIReviewOut,
    DocumentDetailOut,
    DocumentOut,
    DocumentUploadIn,
    HealthItemOut,
    KBCreateIn,
    KBUpdateIn,
    KBReorderIn,
    KBBatchDeleteIn,
    KnowledgeBaseOut,
    KnowledgeBasesResponse,
    SearchDocOut,
)
from app.models.operation_log import record_operation

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/knowledge-bases", response_model=KnowledgeBasesResponse)
async def get_knowledge_bases(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 按 order 列排序（拖拽持久化），同序再按创建时间稳定
    result = await db.execute(
        select(KnowledgeBase).order_by(KnowledgeBase.order, KnowledgeBase.created_at)
    )
    kbs = result.scalars().all()

    # 库级权限：一次性聚合查询，替代原先「每库调一次 get_kb_permission_level」的 N+1
    # （非 admin 用户下，原来每个 KB 触发 1~2 次 DB 查询）。
    # perm_map: kb_id -> 用户自身最高权限；strict_kbs: 存在任意权限记录的库（严格隔离）。
    perm_map: dict[str, str] = {}
    strict_kbs: set[str] = set()
    if user.role != "admin":
        perms = (
            await db.execute(
                select(KBPermission).where(
                    KBPermission.kb_id.in_([kb.id for kb in kbs]),
                    KBPermission.user_id == user.id,
                )
            )
        ).scalars().all()
        for p in perms:
            cur = perm_map.get(p.kb_id)
            if cur is None or LEVEL_ORDER.get(p.level, 0) > LEVEL_ORDER.get(cur, 0):
                perm_map[p.kb_id] = p.level
        any_rows = (
            await db.execute(
                select(KBPermission.kb_id).where(
                    KBPermission.kb_id.in_([kb.id for kb in kbs])
                )
            )
        ).scalars().all()
        strict_kbs = set(any_rows)

    # 一次聚合查询替代「每库 3 次查询」的 N+1 模式：
    # 按 kb_id 汇总 文档数 / 最新更新时间 / 待复核数。
    stats_rows = (
        await db.execute(
            select(
                Document.kb_id,
                func.count(Document.id).label("doc_count"),
                func.max(Document.updated_at).label("latest"),
                func.count(Document.id)
                .filter(Document.status == "待复核")
                .label("pending"),
                func.count(Document.id)
                .filter(Document.status == "已审核")
                .label("approved"),
            ).group_by(Document.kb_id)
        )
    ).all()
    stats_map = {row.kb_id: row for row in stats_rows}

    # 可检索率：统计「有至少 1 个 chunk（已向量化）的文档数」按 kb 分组。
    # 暴露「有文档但 chunker 没切进去 → 搜不到」的坑（如短文本被丢弃）。
    ret_rows = (
        await db.execute(
            select(Document.kb_id, func.count(func.distinct(Document.id)).label("ret"))
            .join(DocChunk, DocChunk.document_id == Document.id)
            .group_by(Document.kb_id)
        )
    ).all()
    ret_map = {row.kb_id: row.ret for row in ret_rows}

    kb_list = []
    health_list = []
    for kb in kbs:
        # 库级权限过滤（权限已上方一次性聚合算出，避免每库一次查询的 N+1）：
        #  - admin / 用户在 perm_map 中有记录 / 遗留开放库（无任何权限记录）→ 可见
        #  - 严格隔离库（存在他人权限记录但用户无记录）→ 不可见
        if user.role != "admin" and kb.id not in perm_map and kb.id in strict_kbs:
            continue

        stat = stats_map.get(kb.id)
        doc_count = stat.doc_count if stat else 0
        latest = stat.latest if stat else None
        pending_count = stat.pending if stat else 0
        approved_count = stat.approved if stat else 0
        retrievable_count = ret_map.get(kb.id, 0)

        # 健康度三维（取代原模糊的 coverage 单值）：
        #  审核率  = 已审核 / 总文档
        #  可检索率 = 有向量(chunk)文档 / 总文档
        #  新鲜度  = 最近更新距现在小时（无文档为 None → 新鲜度分 0）
        review_rate = round(approved_count / doc_count, 2) if doc_count > 0 else 0.0
        retrievable_rate = round(retrievable_count / doc_count, 2) if doc_count > 0 else 0.0
        if latest is not None:
            freshness_hours = round((datetime.now(timezone.utc) - latest).total_seconds() / 3600, 1)
            if freshness_hours < 24:
                freshness_score = 1.0
            elif freshness_hours < 24 * 7:
                freshness_score = 0.8
            elif freshness_hours < 24 * 30:
                freshness_score = 0.5
            elif freshness_hours < 24 * 90:
                freshness_score = 0.3
            else:
                freshness_score = 0.1
        else:
            freshness_hours = None
            freshness_score = 0.0
        # 综合健康分：审核率与可检索率各 0.4，新鲜度 0.2
        health_score = round(review_rate * 0.4 + retrievable_rate * 0.4 + freshness_score * 0.2, 2)

        badge = None
        badge_type = None
        if pending_count and pending_count > 0:
            badge = f"{pending_count} 份待复核"
            badge_type = "danger"

        kb_list.append(
            KnowledgeBaseOut(
                id=kb.id, name=kb.name, icon=kb.icon,
                badge=badge, badge_type=badge_type,
                document_count=doc_count or 0,
                pending_count=pending_count or 0,
                description=kb.description,
                tags=kb.tags or [],
                category=kb.category,
            )
        )
        health_list.append(
            HealthItemOut(
                kb=kb.name,
                doc_count=doc_count or 0,
                updated_at=latest.isoformat() if latest else "",
                review_rate=review_rate,
                retrievable_rate=retrievable_rate,
                freshness_hours=freshness_hours,
                health_score=health_score,
            )
        )

    total = len(kb_list)
    pages = max(1, (total + size - 1) // size) if total else 1
    start = (page - 1) * size
    end = start + size
    return KnowledgeBasesResponse(
        knowledge_bases=kb_list[start:end],
        health=health_list[start:end],
        total=total,
        page=page,
        page_size=size,
        pages=pages,
    )


@router.post("/knowledge-bases", response_model=KnowledgeBaseOut, status_code=201)
async def create_knowledge_base(
    payload: KBCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
):
    """新建知识库。创建者自动获得该库的 admin 级库级权限（隔离起点）。"""
    kb_id = f"kb_{uuid.uuid4().hex[:8]}"
    kb = KnowledgeBase(
        id=kb_id,
        name=payload.name,
        icon=payload.icon or "📚",
        description=payload.description,
    )
    if payload.tags is not None:
        kb.tags = payload.tags
    if payload.category:
        kb.category = payload.category
    # 先落库并提交，再写库级权限。
    # 异步连接池下「同一 commit 内多表写入」可能落到不同物理连接，
    # 导致子表外键看不到未提交的父行而失败；先提交父行可保证
    # knowledge_base 对已提交的子事务全局可见，外键必然可满足。
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    db.add(KBPermission(kb_id=kb_id, user_id=user.id, level="admin"))
    await db.commit()
    await db.refresh(kb)
    return KnowledgeBaseOut(
        id=kb.id, name=kb.name, icon=kb.icon, description=kb.description,
        tags=kb.tags or [], category=kb.category,
    )


@router.get("/knowledge-bases/{kb_id}/documents", response_model=PaginatedOut[DocumentOut])
async def list_documents(
    kb_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    scope: str | None = None,
    doc_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    mine: bool = False,
    department_id: str | None = None,
    tags: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_kb_access("view")),
):
    """列出某知识库下的文档（服务端分页 + 真实过滤）。

    过滤维度：scope（权限范围）/ doc_type（按扩展名）/ status（审核状态）/
    q（标题模糊）/ mine（仅本人）/ department_id（部门维度）/ tags（标签，逗号分隔 OR）。
    返回统一分页结构 {items,total,page,pageSize,pages}。
    """
    base = select(Document).where(Document.kb_id == kb_id)
    if scope:
        base = base.where(Document.scope == scope)
    if doc_type:
        base = base.where(Document.source_path.ilike(f"%{doc_type.lower()}"))
    if status:
        base = base.where(Document.status == status)
    if q:
        base = base.where(Document.title.ilike(f"%{q}%"))
    if mine:
        base = base.where(Document.uploader_id == user.id)
    if department_id:
        try:
            base = base.where(Document.department_id == uuid.UUID(department_id))
        except Exception:
            raise HTTPException(status_code=400, detail="department_id 非法")
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            # JSONB 数组用 ? 存在操作符逐标签匹配，OR 组合实现「含任一标签即命中」
            # （has_any 生成 jsonb ?| jsonb、contains 生成 jsonb @> varchar 均无匹配运算符）
            conds = [Document.tags.has_key(t) for t in tag_list]
            base = base.where(or_(*conds))

    stmt = base.order_by(Document.created_at.desc())
    rows, total = await paginate(db, stmt, page=page, page_size=size)
    pages = max(1, (total + size - 1) // size) if total else 1
    return {
        "items": [_doc_out(r[0]) for r in rows],
        "total": total,
        "page": page,
        "page_size": size,
        "pages": pages,
    }


@router.get("/search/docs", response_model=PaginatedOut[SearchDocOut])
async def search_docs(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    doc_type: str | None = None,
    scope: str | None = None,
    category: str | None = None,
    status: str | None = Query("已审核", description="文档状态"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """全局文档搜索：跨用户有权限的知识库，按标题模糊匹配返回文档卡片。

    用于「智能搜索」页的文档结果列表，支持文件类型 / 分类 / 权限范围 / 状态过滤。
    """
    accessible = await get_accessible_kb_ids(db, user)
    if not accessible:
        return {
            "items": [], "total": 0, "page": page, "page_size": size, "pages": 1,
        }

    kb_ids = [uuid.UUID(x) for x in accessible]
    base = (
        select(Document, KnowledgeBase.name.label("kb_name"))
        .join(KnowledgeBase, KnowledgeBase.id == Document.kb_id)
        .where(Document.kb_id.in_(kb_ids), Document.title.ilike(f"%{q}%"))
    )
    if status:
        base = base.where(Document.status == status)
    if doc_type:
        base = base.where(Document.source_path.ilike(f"%{doc_type.lower()}"))
    if scope:
        base = base.where(Document.scope == scope)
    if category:
        base = base.where(Document.category == category)

    stmt = base.order_by(Document.updated_at.desc())
    rows, total = await paginate(db, stmt, page=page, page_size=size)
    pages = max(1, (total + size - 1) // size) if total else 1

    def _snippet(content: str | None) -> str:
        if not content:
            return ""
        txt = content.replace("\n", " ").strip()
        return txt[:200] + ("..." if len(txt) > 200 else "")

    return {
        "items": [
            SearchDocOut(
                id=str(d.id),
                title=d.title,
                type=_doc_type(d.source_path),
                status=d.status,
                updated_at=d.updated_at.isoformat() if d.updated_at else "",
                kb_id=str(d.kb_id),
                kb_name=kb_name or "",
                category=d.category,
                scope=d.scope,
                uploader_name=d.uploader_name,
                snippet=_snippet(d.content_md),
            )
            for d, kb_name in rows
        ],
        "total": total,
        "page": page,
        "page_size": size,
        "pages": pages,
    }


@router.get("/knowledge-bases/{kb_id}/tags")
async def list_doc_tags(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("view")),
):
    """返回该知识库文档中出现过的去重标签，供前端标签筛选下拉枚举。"""
    rows = (await db.execute(select(Document.tags).where(Document.kb_id == kb_id))).scalars().all()
    tag_set: set[str] = set()
    for t in rows:
        if t:
            tag_set.update(t)
    return sorted(tag_set)


@router.post("/knowledge-bases/{kb_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    kb_id: str,
    payload: DocumentUploadIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_kb_access("edit")),
):
    """上传单篇文档（.md / .txt / .docx / .pdf）—— 方案 A（延迟摄入）。

    只做三件事，不切分、不向量化、不进检索库：
      1) 原始字节存入对象存储（key 含 uuid 防重名；source_path 记录位置用于溯源/重解析）
      2) 按扩展名解析为纯文本，落 content_md（供审核后摄入复用，无需重新解析）
      3) 建 Document(status=待复核)，写入 original_filename / file_size 留痕
    这样未审核文档在检索侧天然不可见（retriever 只从 DocChunk 捞数据），
    审核通过后再由 approve 接口触发 ingest_existing 真正摄入。
    前端把文件读成 base64（content_b64）提交；文本文件仍兼容旧的 content 字段。
    """
    kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    filename = payload.filename or "untitled"

    # 1) 还原原始字节：优先二进制（base64），其次文本路径（向后兼容）
    if payload.content_b64:
        try:
            raw = base64.b64decode(payload.content_b64, validate=True)
        except Exception:
            raise HTTPException(status_code=422, detail="content_b64 不是合法 base64")
    elif payload.content is not None:
        raw = payload.content.encode("utf-8")
    else:
        raise HTTPException(status_code=422, detail="content 与 content_b64 至少提供其一")

    # 1b) 大小防护：解码后原始字节上限 20MB，防止超大/恶意文件撑爆内存
    #     （PDF/DOCX 解析还会进一步放大，故在落库前拦截）
    MAX_UPLOAD_BYTES = 20 * 1024 * 1024
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件过大，单篇上传上限 20MB")

    # 2) 原始文件落对象存储（key 含 uuid 防重名；source_path 记录其位置用于溯源）
    store = get_object_store()
    object_key = f"uploads/{kb_id}/{uuid.uuid4().hex}_{filename}"
    await store.put(object_key, raw)

    # 3) 按扩展名解析：文本走原 parse_document；图片/音频/视频走多模态解析器。
    #    解析失败则清理已存的原始文件并回 415。
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    text_exts = {"md", "markdown", "txt", "docx", "pdf"}
    if ext in text_exts:
        try:
            parsed = parse_document(filename, raw)
        except UnsupportedFormatError as e:
            await store.delete(object_key)
            raise HTTPException(status_code=415, detail=str(e))
    elif ext in IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS:
        try:
            parsed = await parse_multimodal(filename, raw, get_llm())
        except UnsupportedFormatError as e:
            await store.delete(object_key)
            raise HTTPException(status_code=415, detail=str(e))
    else:
        await store.delete(object_key)
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件格式 .{ext or '未知'}，当前支持：md / txt / docx / pdf / 图片 / 音频 / 视频",
        )

    # 4) 方案 A：只建 Document(status=待复核)，不摄入
    title = _extract_title(parsed.text, filename)
    # P0：权限范围校验（信任边界），非法值归 public
    scope = payload.scope or "public"
    if scope not in ("private", "department", "company", "public"):
        scope = "public"
    doc = Document(
        kb_id=kb_id,
        title=title,
        source_path=object_key,
        content_md=parsed.text,
        status="待复核",
        original_filename=filename,
        file_size=len(raw),
        # P0：真实三要素
        uploader_id=user.id,
        uploader_name=user.display_name,
        scope=scope,
        parse_status="pending",
    )
    # 标签 / 分类 / 归属部门（架构图1/2/5：随上传透传）
    if payload.tags is not None:
        doc.tags = payload.tags
    if payload.category:
        doc.category = payload.category
    if payload.department_id:
        try:
            doc.department_id = uuid.UUID(payload.department_id)
        except Exception:
            raise HTTPException(status_code=400, detail="department_id 非法")
    db.add(doc)
    # 先 flush 让 doc.id 生成，否则 task.document_id 会拿到 None（FK 落空）
    await db.flush()
    # 建立处理任务记录（架构图6：异步处理状态跟踪，前端轮询进度）
    # 方案 A 下上传即完成解析，故任务直接落到「解析完成」(progress=100)；
    # 审核通过(approve)时会再次推进到 processing(50)→completed(100) 表示摄入完成。
    task = DocumentTask(
        document_id=doc.id,
        kb_id=kb_id,
        filename=filename,
        status="done",
        progress=100,
        current_step="解析完成，待审核",
    )
    db.add(task)
    await db.commit()
    await db.refresh(doc)
    await record_operation(db, user, "upload", related_doc_id=str(doc.id), detail=filename)

    return _doc_out(doc)


def _doc_out(d: Document) -> DocumentOut:
    """统一把 Document 行序列化成 DocumentOut（列表/上传/审核后共用）。"""
    return DocumentOut(
        id=str(d.id),
        title=d.title,
        type=_doc_type(d.source_path),
        size_kb=round((d.file_size or len(d.content_md.encode("utf-8", errors="ignore"))) / 1024, 2),
        status=d.status,
        updated_at=d.updated_at.isoformat() if d.updated_at else "",
        original_filename=d.original_filename,
        file_size=d.file_size,
        tags=d.tags or [],
        category=d.category,
        department_id=str(d.department_id) if d.department_id else None,
        uploader_name=d.uploader_name,
        scope=d.scope,
        parse_status=d.parse_status,
    )


@router.get("/knowledge-bases/{kb_id}/documents/{doc_id}", response_model=DocumentDetailOut)
async def get_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("view")),
):
    """文档详情：返回解析后的 content_md（溯源/预览/审核查看用）。"""
    doc = await db.scalar(select(Document).where(Document.id == doc_id, Document.kb_id == kb_id))
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentDetailOut(
        id=str(doc.id),
        title=doc.title,
        type=_doc_type(doc.source_path),
        status=doc.status,
        content_md=doc.content_md,
        original_filename=doc.original_filename,
        file_size=doc.file_size,
        updated_at=doc.updated_at.isoformat() if doc.updated_at else "",
        reviewed_at=doc.reviewed_at.isoformat() if doc.reviewed_at else None,
        reviewed_by=doc.reviewed_by,
    )


@router.post("/knowledge-bases/{kb_id}/documents/{doc_id}/approve", response_model=DocumentOut)
async def approve_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_kb_access("edit")),
):
    """审核通过：翻转状态为已审核，并触发摄入（切分+向量化+ES+图谱）。

    方案 A 的核心入口：上传时只落库不摄入，检索侧天然隔离未审核内容；
    这里才真正把文档纳入检索库。幂等：已是「已审核」直接返回，不重复摄入。
    """
    doc = await db.scalar(select(Document).where(Document.id == doc_id, Document.kb_id == kb_id))
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if doc.status == "已审核":
        return _doc_out(doc)  # 幂等：已审核不再重复摄入

    doc.status = "已审核"
    doc.reviewed_at = datetime.now(timezone.utc)
    doc.reviewed_by = str(user.id)
    doc.parse_status = "done"  # P0：审核通过即解析完成
    await db.flush()

    # 处理任务：进入处理中（前端据此推进进度条）
    task = await db.scalar(
        select(DocumentTask)
        .where(DocumentTask.document_id == doc.id)
        .order_by(DocumentTask.created_at.desc())
    )
    if task is not None:
        task.status = "processing"
        task.progress = 50
        task.current_step = "向量化中"
        task.started_at = datetime.now(timezone.utc)

    # 触发摄入：生产走后台异步，不阻塞请求（大文档同步摄入会触发网关 504）。
    # ponytail: 测试环境同步摄入，避免依赖后台任务调度时序（CI 冷启动
    # postgres 较慢，原 3s 轮询超时会导致测试偶发失败）；生产仍异步不阻塞。
    if settings.APP_ENV == "test":
        await _ingest_document_background(kb_id, doc.id, str(user.id))
    else:
        _spawn_background(_ingest_document_background(kb_id, doc.id, str(user.id)))

    await db.commit()  # 持久化 status=已审核 + task=processing，前端立即可见进度
    await db.refresh(doc)
    await record_operation(db, user, "approve", related_doc_id=str(doc.id), detail=doc.title)
    return _doc_out(doc)


# 后台任务引用集：与 agent.py 同款机制，持有 task 到完成，防止被 GC 取消
_BACKGROUND_TASKS: set = set()


def _spawn_background(coro):
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


async def _ingest_document_background(kb_id: str, doc_id: str, user_id: str) -> None:
    """审核通过后异步摄入：切分+向量化+ES+图谱，回写处理任务进度。

    ponytail: 不阻塞 approve 请求（大文档同步摄入会触发网关 504）；
    独立 DB 会话 + 单例依赖，失败隔离，不污染主请求事务。
    """
    async with AsyncSessionLocal() as db:
        doc = await db.scalar(
            select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
        )
        if doc is None:
            return
        ingester = DocumentIngester(
            get_embedder(),
            settings.RAG_CHUNK_SIZE,
            settings.RAG_CHUNK_OVERLAP,
            settings.RAG_CHUNK_MIN_CHARS,
            es=get_es(),
            graph=GraphStore(get_llm(), get_embedder()),
        )
        task = await db.scalar(
            select(DocumentTask)
            .where(DocumentTask.document_id == doc.id)
            .order_by(DocumentTask.created_at.desc())
        )
        try:
            await ingester.ingest_existing(doc, db)
            if task is not None:
                task.status = "completed"
                task.progress = 100
                task.current_step = "完成"
                task.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as e:
            logger.warning("background ingest failed kb=%s doc=%s: %s", kb_id, doc_id, e)
            if task is not None:
                task.status = "failed"
                task.current_step = "摄入失败"
                await db.commit()


@router.post("/knowledge-bases/{kb_id}/documents/{doc_id}/reject", response_model=DocumentOut)
async def reject_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_kb_access("edit")),
):
    """审核驳回：状态改为已拒绝，保留原始文件与解析文本留痕，但不摄入（不进检索库）。"""
    doc = await db.scalar(select(Document).where(Document.id == doc_id, Document.kb_id == kb_id))
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    doc.status = "已拒绝"
    doc.reviewed_at = datetime.now(timezone.utc)
    doc.reviewed_by = str(user.id)
    doc.parse_status = "failed"  # P0：驳回即解析失败（不进检索库）
    # 处理任务：标记为失败（已驳回）
    task = await db.scalar(
        select(DocumentTask)
        .where(DocumentTask.document_id == doc.id)
        .order_by(DocumentTask.created_at.desc())
    )
    if task is not None:
        task.status = "failed"
        task.current_step = "已驳回"
        task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(doc)
    await record_operation(db, user, "reject", related_doc_id=str(doc.id), detail=doc.title)
    return _doc_out(doc)


@router.post("/knowledge-bases/{kb_id}/documents/{doc_id}/ai-review", response_model=AIReviewOut)
async def ai_review_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    embedder: EmbeddingModel = Depends(get_embedder),
    llm: OpenAICompatProvider = Depends(get_llm),
    _: User = Depends(require_kb_access("view")),
):
    """AI 辅助审核：相似度检索 + LLM 结构化建议。只读分析，不写库。"""
    from app.core.rag.ai_review import ai_review_document as _review

    result = await _review(kb_id, doc_id, db, embedder, llm)
    if result is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    # 对齐 Pydantic camelCase 输出
    return {
        "verdict": result["verdict"],
        "summary": result["summary"],
        "duplicates": result["duplicates"],
        "outdatedFindings": result["outdated_findings"],
        "qualityNotes": result["quality_notes"],
        "suggestedKb": result["suggested_kb"],
        "similarityFindings": [
            {
                "similarity": f["similarity"],
                "docTitle": f["docTitle"],
                "docId": f["docId"],
                "snippet": f["snippet"],
                "matchedChunk": f["matchedChunk"],
            }
            for f in result.get("similarity_findings", [])
        ],
    }


@router.delete("/knowledge-bases/{kb_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_kb_access("edit")),
):
    """删除文档：级联清理 chunk / ES 索引 / 图谱节点 / 对象存储原始文件。

    顺序很关键：先取 chunk_id → 删图节点（引用 chunk_id）→ 删 DocChunk
    （FK 必须在删 Document 之前清）→ 删 ES → 删对象存储 → 最后删 Document。
    """
    doc = await db.scalar(select(Document).where(Document.id == doc_id, Document.kb_id == kb_id))
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 1) 取该文档的全部 chunk id（删图节点 / 删 ES 前先取）
    chunk_ids = (
        await db.execute(select(DocChunk.id).where(DocChunk.document_id == doc.id))
    ).scalars().all()

    # 2) 删图谱节点（按 chunk_id 归属）
    await GraphStore().delete_by_doc(db, kb_id, chunk_ids)

    # 3) 删 DocumentTask（FK 必须在删 DocChunk/Document 前清）
    await db.execute(delete(DocumentTask).where(DocumentTask.document_id == doc.id))

    # 4) 删 DocChunk（FK 必须在删 Document 前清，否则违反外键）
    await db.execute(delete(DocChunk).where(DocChunk.document_id == doc.id))

    # 5) 删 ES 索引里的该文档 chunk（ES 不可用时静默跳过）
    await ESClient().delete_by_doc(kb_id, str(doc.id))

    # 6) 删对象存储原始文件（缺失不阻断删除）
    store = get_object_store()
    try:
        await store.delete(doc.source_path)
    except Exception:
        pass

    # 7) 删文档本身
    await db.delete(doc)
    await db.commit()
    await record_operation(db, user, "delete", related_doc_id=str(doc.id), detail=doc.title)


_TYPE_MAP = {
    "md": "MD",
    "markdown": "MD",
    "txt": "TXT",
    "docx": "DOCX",
    "pdf": "PDF",
    # Phase 7 多模态：图片/音频/视频的类型徽标
    "png": "IMAGE", "jpg": "IMAGE", "jpeg": "IMAGE", "gif": "IMAGE",
    "bmp": "IMAGE", "webp": "IMAGE",
    "mp3": "AUDIO", "wav": "AUDIO", "m4a": "AUDIO", "ogg": "AUDIO",
    "flac": "AUDIO", "aac": "AUDIO",
    "mp4": "VIDEO", "mov": "VIDEO", "webm": "VIDEO", "mkv": "VIDEO", "avi": "VIDEO",
}


def _doc_type(source_path: str) -> str:
    """按文件名/存储 key 的扩展名推断文档类型（覆盖 md/txt/docx/pdf）。"""
    ext = source_path.rsplit(".", 1)[-1].lower() if "." in source_path else "txt"
    return _TYPE_MAP.get(ext, "TXT")


def _extract_title(content: str, fallback: str) -> str:
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


async def _delete_kb_cascade(db: AsyncSession, kb_id: str) -> None:
    """级联删除知识库：先清其下所有文档（chunk/ES/图谱/对象存储），
    再清库级权限与库本身。

    顺序关键：先取 chunk_id → 删图节点 → 删 DocChunk（FK 必须在删
    Document 前清）→ 删 ES → 删对象存储 → 删 Document → 删权限 → 删库。
    ES / 图谱连接失败时静默跳过，不阻断删除——生产环境 ES 偶发
    抖动不应导致删库失败，测试环境无 ES 也能跑通。
    """
    docs = (await db.execute(select(Document).where(Document.kb_id == kb_id))).scalars().all()
    store = get_object_store()
    for doc in docs:
        chunk_ids = (
            await db.execute(select(DocChunk.id).where(DocChunk.document_id == doc.id))
        ).scalars().all()
        # 删图谱节点（按 chunk_id 归属），连接失败静默跳过
        try:
            await GraphStore().delete_by_doc(db, kb_id, chunk_ids)
        except Exception:
            pass
        # 先清 DocumentTask，再清 DocChunk，最后删 Document，避免 FK 冲突
        await db.execute(delete(DocumentTask).where(DocumentTask.document_id == doc.id))
        # 删 DocChunk（FK 必须在删 Document 前清，否则违反外键）
        await db.execute(delete(DocChunk).where(DocChunk.document_id == doc.id))
        # 删 ES 索引，连接失败静默跳过
        try:
            await get_es().delete_by_doc(kb_id, str(doc.id))
        except Exception:
            pass
        # 删对象存储原始文件，缺失不阻断删除
        try:
            await store.delete(doc.source_path)
        except Exception:
            pass
        await db.delete(doc)
    # 清库级权限
    await db.execute(delete(KBPermission).where(KBPermission.kb_id == kb_id))
    # 删库本身
    await db.execute(delete(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    await db.commit()


@router.put("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(
    kb_id: str,
    payload: KBUpdateIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("admin")),
):
    """编辑知识库：更新名称 / 图标 / 描述（库 admin 级或全局 admin 可执行）。"""
    kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if payload.name is not None:
        kb.name = payload.name
    if payload.icon is not None:
        kb.icon = payload.icon
    if payload.description is not None:
        kb.description = payload.description
    if payload.tags is not None:
        kb.tags = payload.tags
    if payload.category is not None:
        kb.category = payload.category
    await db.commit()
    await db.refresh(kb)
    return KnowledgeBaseOut(
        id=kb.id, name=kb.name, icon=kb.icon, description=kb.description,
        tags=kb.tags or [], category=kb.category,
    )


@router.delete("/knowledge-bases/{kb_id}", status_code=204)
async def delete_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("admin")),
):
    """删除知识库：级联清理其下文档 / chunk / ES / 图谱 / 对象存储 / 库级权限。"""
    kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    await _delete_kb_cascade(db, kb_id)


@router.post("/knowledge-bases/reorder")
async def reorder_knowledge_bases(
    payload: KBReorderIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    """拖拽排序：前端传回当前列表的完整 id 顺序，后端按数组下标赋 order。

    全局排序操作无单一 kb_id，故用 require_roles 限制为全局 admin。
    """
    kbs = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(payload.ordered_ids)))
    ).scalars().all()
    pos = {kid: i for i, kid in enumerate(payload.ordered_ids)}
    for kb in kbs:
        kb.order = pos.get(kb.id, kb.order)
    await db.commit()
    return {"ok": True}


@router.post("/knowledge-bases/batch-delete", status_code=204)
async def batch_delete_knowledge_bases(
    payload: KBBatchDeleteIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    """批量删除知识库：对每个 id 走与单删相同的级联清理。"""
    for kb_id in payload.ids:
        kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        if kb:
            await _delete_kb_cascade(db, kb_id)
