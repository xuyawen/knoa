"""文档路由：列表 / 全局搜索 / 标签枚举 / 上传（方案 A 延迟摄入）/ 详情 / 删除。"""
import asyncio
import base64
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.graph import GraphStore
from app.core.pagination import paginate
from app.core.ratelimit import rate_limit
from app.core.rag.multimodal import (
    AUDIO_EXTS,
    IMAGE_EXTS,
    VIDEO_EXTS,
    parse_multimodal,
)
from app.core.rag.parsers import UnsupportedFormatError, parse_document
from app.core.security import (
    LEVEL_ORDER,
    ScopeContext,
    compute_visible_dept_ids,
    doc_scope_clause,
    ensure_doc_scope_writable,
    get_accessible_kb_ids,
    get_current_user,
    get_kb_permission_level,
    is_scope_visible,
    is_super_admin,
    require_kb_access,
)
from app.core.storage import get_object_store
from app.db import DocChunk, Document, DocumentTask, KnowledgeBase, User
from app.deps import get_db, get_es, get_llm
from app.models.common import PaginatedOut
from app.models.knowledge import (
    DocumentDetailOut,
    DocumentOut,
    DocumentUploadIn,
    SearchDocOut,
)
from app.models.operation_log import record_operation
from app.routers.knowledge.common import doc_out, doc_type, extract_title

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/knowledge-bases/{kb_id}/documents", response_model=PaginatedOut[DocumentOut])
async def list_documents(
    kb_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    scope: str | None = None,
    doc_type_filter: str | None = Query(None, alias="doc_type"),
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
    # scope 补全：强制可见性过滤——非该库 admin 仅见 public-like 及自己的 private 文档，
    # 取代旧「前端传 scope 才过滤」的可选逻辑（不传则私有文档也会暴露）
    _level = await get_kb_permission_level(db, kb_id, user)
    _is_admin = _level == "admin"
    _dept_ids = frozenset() if _is_admin else await compute_visible_dept_ids(db, user)
    _clause = doc_scope_clause(user, _is_admin, _dept_ids)
    if _clause is not None:
        base = base.where(_clause)
    if scope:
        base = base.where(Document.scope == scope)
    if doc_type_filter:
        base = base.where(Document.source_path.ilike(f"%{doc_type_filter.lower()}"))
    if status:
        base = base.where(Document.status == status)
    if q:
        base = base.where(Document.title.ilike(f"%{q}%"))
    if mine:
        base = base.where(Document.uploader_id == user.id)
    if department_id:
        try:
            base = base.where(Document.department_id == uuid.UUID(department_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="department_id 非法") from None
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
        "items": [doc_out(r[0]) for r in rows],
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
    doc_type_filter: str | None = Query(None, alias="doc_type"),
    scope: str | None = None,
    category: str | None = None,
    status: str | None = Query("已审核", description="文档状态"),
    updated_after: str | None = Query(None, description="更新时间过滤：7d/30d/90d/180d"),
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

    base = (
        select(Document, KnowledgeBase.name.label("kb_name"))
        .join(KnowledgeBase, KnowledgeBase.id == Document.kb_id)
        .where(Document.kb_id.in_(accessible), Document.title.ilike(f"%{q}%"))
    )
    # scope 补全：全局搜索强制可见性过滤（仅超管豁免）
    _is_admin = await is_super_admin(db, user)
    _dept_ids = frozenset() if _is_admin else await compute_visible_dept_ids(db, user)
    _clause = doc_scope_clause(user, _is_admin, _dept_ids)
    if _clause is not None:
        base = base.where(_clause)
    if status:
        base = base.where(Document.status == status)
    if doc_type_filter:
        base = base.where(Document.source_path.ilike(f"%{doc_type_filter.lower()}"))
    if scope:
        base = base.where(Document.scope == scope)
    if category:
        base = base.where(Document.category == category)
    if updated_after:
        days_map = {"7d": 7, "30d": 30, "90d": 90, "180d": 180}
        days = days_map.get(updated_after)
        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            base = base.where(Document.updated_at >= cutoff)

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
                type=doc_type(d.source_path),
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
    _rl: None = Depends(rate_limit(20, 60, "upload")),  # 每用户 60s 内最多 20 次上传
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

    # 文件名清洗：去除路径分隔符，防止 object key 逃逸到意外目录（存储层另有 `..` 兜底）
    filename = (payload.filename or "untitled").replace("\\", "/").split("/")[-1] or "untitled"

    # 1) 还原原始字节：三种来源
    #    a) file_url：前端已直传到 OSS，后端按 URL 回抓字节（仅存 URL，不落本地存储）
    #    b) content_b64：二进制 base64（向后兼容旧前端流程）
    #    c) content：纯文本（md/txt 直传）
    source_path: str | None = None
    if payload.file_url:
        try:
            from app.core.oss import normalize_url
            from app.core.rag.fetchers import fetch_url_bytes
            source_path = normalize_url(payload.file_url)  # SSRF 校验：必须是本 OSS 桶地址
            raw = await fetch_url_bytes(source_path, max_bytes=settings.OSS_MAX_SIZE or 100 * 1024 * 1024)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"file_url 非法：{e}") from e
        except Exception as e:  # noqa: BLE001  (intentional catch-all: convert any OSS fetch failure to 502)
            raise HTTPException(status_code=502, detail=f"从 OSS 拉取文件失败：{e}") from e
    elif payload.content_b64:
        try:
            # 大文件 base64 解码是纯 CPU 操作（百 MB 级可达百毫秒），移出事件循环
            raw = await asyncio.to_thread(base64.b64decode, payload.content_b64, validate=True)
        except Exception:  # noqa: BLE001  (intentional catch-all: return 422 if content_b64 not valid base64)
            raise HTTPException(status_code=422, detail="content_b64 不是合法 base64") from None
    elif payload.content is not None:
        raw = payload.content.encode("utf-8")
    else:
        raise HTTPException(status_code=422, detail="content / content_b64 / file_url 至少提供其一")

    # 1b) 大小防护：解码后原始字节上限（OSS 直传走 OSS_MAX_SIZE，旧流程保持 20MB）
    MAX_UPLOAD_BYTES = settings.OSS_MAX_SIZE or (20 * 1024 * 1024)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件过大，单篇上传上限超限")

    # 2) 原始文件落存储：OSS 直传场景 source_path 已是可访问 URL（不重复落本地库），
    #    旧流程才把字节写入对象存储并记 key 用于溯源/重解析。
    store = None
    object_key = None
    if source_path is None:
        store = get_object_store()
        object_key = f"uploads/{kb_id}/{uuid.uuid4().hex}_{filename}"
        await store.put(object_key, raw)
        source_path = object_key

    # 3) 按扩展名解析：文本走原 parse_document；图片/音频/视频走多模态解析器。
    #    解析失败则清理已存的原始文件并回 415（仅本地存储时才需清理）。
    async def _cleanup():
        if store is not None and object_key:
            try:
                await store.delete(object_key)
            except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, ignore cleanup delete errors)
                pass

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    text_exts = {"md", "markdown", "txt", "docx", "pdf"}
    if ext in text_exts:
        try:
            # pdf/docx 解析是重 CPU 操作（大文档可达秒级），移出事件循环，
            # 否则会阻塞全部并发请求（含 SSE 流心跳）
            parsed = await asyncio.to_thread(parse_document, filename, raw)
        except UnsupportedFormatError as e:
            await _cleanup()
            raise HTTPException(status_code=415, detail=str(e)) from e
    elif ext in IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS:
        try:
            parsed = await parse_multimodal(filename, raw, get_llm())
        except UnsupportedFormatError as e:
            await _cleanup()
            raise HTTPException(status_code=415, detail=str(e)) from e
    else:
        await _cleanup()
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件格式 .{ext or '未知'}，当前支持：md / txt / docx / pdf / 图片 / 音频 / 视频",
        )

    # 4) 方案 A：只建 Document(status=待复核)，不摄入
    title = extract_title(parsed.text, filename)
    # P0：权限范围校验（信任边界），非法值归 public
    scope = payload.scope or "public"
    if scope not in ("private", "department", "public"):
        scope = "public"
    doc = Document(
        kb_id=kb_id,
        title=title,
        source_path=source_path,
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
    # 归属部门：显式传 department_id 优先；scope=department 未传则默认取上传者部门。
    # department 文档必须有部门（否则无人可见），两者皆空 → 400。
    if payload.department_id:
        try:
            doc.department_id = uuid.UUID(payload.department_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="department_id 非法") from None
    elif scope == "department":
        if user.department_id is None:
            raise HTTPException(
                status_code=400, detail="部门文档需指定部门，且当前用户无部门可默认"
            )
        doc.department_id = user.department_id
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

    return doc_out(doc)


@router.get("/documents/{doc_id}", response_model=DocumentDetailOut)
async def get_document_by_id(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """按文档 id 直接取详情（操作审计/问答溯源点击预览用）。

    文档 id 全局唯一，这里先查出文档得到 kb_id，再走和按 kb 查一样的
    权限校验（admin 可见全部；其余用户须对该 kb 有 view 权限）。
    """
    doc = await db.scalar(select(Document).where(Document.id == doc_id))
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    level = await get_kb_permission_level(db, doc.kb_id, user)
    if level is None or LEVEL_ORDER.get(level, 0) < LEVEL_ORDER.get("view", 0):
        raise HTTPException(status_code=403, detail="无权访问该文档")
    # scope 补全：库级 view 之上再校验文档级可见性（private 仅上传者，department 命中部门子树，admin 豁免）
    _is_admin = level == "admin"
    _dept_ids = frozenset() if _is_admin else await compute_visible_dept_ids(db, user)
    if not is_scope_visible(
        doc.scope, doc.uploader_id,
        ScopeContext(str(user.id), _is_admin, _dept_ids),
        str(doc.department_id) if doc.department_id else None,
    ):
        raise HTTPException(status_code=403, detail="无权访问该文档")
    return DocumentDetailOut(
        id=str(doc.id),
        title=doc.title,
        type=doc_type(doc.source_path),
        status=doc.status,
        content_md=doc.content_md,
        original_filename=doc.original_filename,
        file_size=doc.file_size,
        updated_at=doc.updated_at.isoformat() if doc.updated_at else "",
        reviewed_at=doc.reviewed_at.isoformat() if doc.reviewed_at else None,
        reviewed_by=doc.reviewed_by,
    )


@router.get("/knowledge-bases/{kb_id}/documents/{doc_id}", response_model=DocumentDetailOut)
async def get_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_kb_access("view")),
):
    """文档详情：返回解析后的 content_md（溯源/预览/审核查看用）。"""
    doc = await db.scalar(select(Document).where(Document.id == doc_id, Document.kb_id == kb_id))
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    # scope 补全：库级 view 之上再校验文档级可见性（private 仅上传者，department 命中部门子树，admin 豁免）
    level = await get_kb_permission_level(db, kb_id, user)
    _is_admin = level == "admin"
    _dept_ids = frozenset() if _is_admin else await compute_visible_dept_ids(db, user)
    if not is_scope_visible(
        doc.scope, doc.uploader_id,
        ScopeContext(str(user.id), _is_admin, _dept_ids),
        str(doc.department_id) if doc.department_id else None,
    ):
        raise HTTPException(status_code=403, detail="无权访问该文档")
    return DocumentDetailOut(
        id=str(doc.id),
        title=doc.title,
        type=doc_type(doc.source_path),
        status=doc.status,
        content_md=doc.content_md,
        original_filename=doc.original_filename,
        file_size=doc.file_size,
        updated_at=doc.updated_at.isoformat() if doc.updated_at else "",
        reviewed_at=doc.reviewed_at.isoformat() if doc.reviewed_at else None,
        reviewed_by=doc.reviewed_by,
    )


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

    # scope 补全：库级 edit 之上再校验文档级可见性，堵住"有库 edit 删别人 private"越权
    await ensure_doc_scope_writable(db, doc, user)

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

    # 5) 删 ES 索引里的该文档 chunk（复用单例连接池；ES 不可用时静默跳过）
    await get_es().delete_by_doc(kb_id, str(doc.id))

    # 6) 删对象存储原始文件（缺失不阻断删除）
    store = get_object_store()
    try:
        await store.delete(doc.source_path)
    except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, ignore object-store delete error)
        pass

    # 7) 删文档本身
    await db.delete(doc)
    await db.commit()
    await record_operation(db, user, "delete", related_doc_id=str(doc.id), detail=doc.title)
