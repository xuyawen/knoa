import base64
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.graph import GraphStore
from app.core.llm.openai_compat import OpenAICompatProvider
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.es_client import ESClient
from app.core.rag.ingestor import DocumentIngester
from app.core.rag.parsers import UnsupportedFormatError, parse_document
from app.core.storage import get_object_store
from app.config import settings
from app.core.security import (
    get_current_user,
    get_kb_permission_level,
    require_kb_access,
    require_roles,
)
from app.db import DocChunk, Document, KBPermission, KnowledgeBase, User
from app.deps import get_db, get_embedder, get_llm
from app.models.knowledge import (
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
)

router = APIRouter()


@router.get("/knowledge-bases", response_model=KnowledgeBasesResponse)
async def get_knowledge_bases(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 按 order 列排序（拖拽持久化），同序再按创建时间稳定
    result = await db.execute(
        select(KnowledgeBase).order_by(KnowledgeBase.order, KnowledgeBase.created_at)
    )
    kbs = result.scalars().all()

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
        # 库级权限过滤：无权限则对用户不可见
        if await get_kb_permission_level(db, kb.id, user) is None:
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

    return KnowledgeBasesResponse(knowledge_bases=kb_list, health=health_list)


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
    return KnowledgeBaseOut(id=kb.id, name=kb.name, icon=kb.icon)


@router.get("/knowledge-bases/{kb_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("view")),
):
    """列出某知识库下的文档。"""
    result = await db.execute(
        select(Document).where(Document.kb_id == kb_id).order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [_doc_out(d) for d in docs]


@router.post("/knowledge-bases/{kb_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    kb_id: str,
    payload: DocumentUploadIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("edit")),
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

    # 2) 原始文件落对象存储（key 含 uuid 防重名；source_path 记录其位置用于溯源）
    store = get_object_store()
    object_key = f"uploads/{kb_id}/{uuid.uuid4().hex}_{filename}"
    await store.put(object_key, raw)

    # 3) 按扩展名解析为文本；解析失败则清理已存的原始文件并回 415
    try:
        parsed = parse_document(filename, raw)
    except UnsupportedFormatError as e:
        await store.delete(object_key)
        raise HTTPException(status_code=415, detail=str(e))

    # 4) 方案 A：只建 Document(status=待复核)，不摄入
    title = _extract_title(parsed.text, filename)
    doc = Document(
        kb_id=kb_id,
        title=title,
        source_path=object_key,
        content_md=parsed.text,
        status="待复核",
        original_filename=filename,
        file_size=len(raw),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

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
    embedder: EmbeddingModel = Depends(get_embedder),
    llm: OpenAICompatProvider = Depends(get_llm),
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
    await db.flush()

    # 触发摄入：与 seed / upload 共用同一套 chunk/embed/ES/图谱逻辑
    ingester = DocumentIngester(
        embedder,
        settings.RAG_CHUNK_SIZE,
        settings.RAG_CHUNK_OVERLAP,
        settings.RAG_CHUNK_MIN_CHARS,
        es=ESClient(),
        graph=GraphStore(llm, embedder),
    )
    await ingester.ingest_existing(doc, db)
    await db.refresh(doc)
    return _doc_out(doc)


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
    await db.commit()
    await db.refresh(doc)
    return _doc_out(doc)


@router.delete("/knowledge-bases/{kb_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("edit")),
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

    # 3) 删 DocChunk（FK 必须在删 Document 前清，否则违反外键）
    await db.execute(delete(DocChunk).where(DocChunk.document_id == doc.id))

    # 4) 删 ES 索引里的该文档 chunk（ES 不可用时静默跳过）
    await ESClient().delete_by_doc(kb_id, str(doc.id))

    # 5) 删对象存储原始文件（缺失不阻断删除）
    store = get_object_store()
    try:
        await store.delete(doc.source_path)
    except Exception:
        pass

    # 6) 删文档本身
    await db.delete(doc)
    await db.commit()


_TYPE_MAP = {
    "md": "MD",
    "markdown": "MD",
    "txt": "TXT",
    "docx": "DOCX",
    "pdf": "PDF",
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
        # 删 DocChunk（FK 必须在删 Document 前清，否则违反外键）
        await db.execute(delete(DocChunk).where(DocChunk.document_id == doc.id))
        # 删 ES 索引，连接失败静默跳过
        try:
            await ESClient().delete_by_doc(kb_id, str(doc.id))
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
    await db.commit()
    await db.refresh(kb)
    return KnowledgeBaseOut(
        id=kb.id, name=kb.name, icon=kb.icon, description=kb.description
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
