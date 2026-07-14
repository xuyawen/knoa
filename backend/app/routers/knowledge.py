import base64
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.graph import GraphStore
from app.core.llm.openai_compat import OpenAICompatProvider
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.es_client import ESClient
from app.core.rag.ingestor import DocumentIngester
from app.core.rag.parsers import UnsupportedFormatError, parse_document
from app.core.storage import get_object_store
from app.core.security import (
    get_current_user,
    get_kb_permission_level,
    require_kb_access,
    require_roles,
)
from app.db import DocChunk, Document, KBPermission, KnowledgeBase, User
from app.deps import get_db, get_embedder, get_llm
from app.models.knowledge import (
    DocumentOut,
    DocumentUploadIn,
    HealthItemOut,
    KBCreateIn,
    KnowledgeBaseOut,
    KnowledgeBasesResponse,
)

router = APIRouter()

# ponytail: Phase 1 覆盖率用固定映射, 真实系统按检索命中/文档时效计算
COVERAGE_MAP = {
    "compliance": 0.82,
    "ads": 0.76,
    "logistics": 0.69,
    "selection": 0.61,
    "service": 0.55,
}


@router.get("/knowledge-bases", response_model=KnowledgeBasesResponse)
async def get_knowledge_bases(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at))
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
            ).group_by(Document.kb_id)
        )
    ).all()
    stats_map = {row.kb_id: row for row in stats_rows}

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

        badge = None
        badge_type = None
        if pending_count and pending_count > 0:
            badge = f"{pending_count} 份待复核"
            badge_type = "danger"

        kb_list.append(
            KnowledgeBaseOut(
                id=kb.id, name=kb.name, icon=kb.icon,
                badge=badge, badge_type=badge_type,
            )
        )
        health_list.append(
            HealthItemOut(
                kb=kb.name,
                doc_count=doc_count or 0,
                updated_at=latest.isoformat() if latest else "",
                coverage=COVERAGE_MAP.get(kb.id, 0.5),
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
    return [
        DocumentOut(
            id=str(d.id),
            title=d.title,
            type=_doc_type(d.source_path),
            size_kb=round(len(d.content_md.encode("utf-8", errors="ignore")) / 1024, 2),
            status=d.status,
            updated_at=d.updated_at.isoformat() if d.updated_at else "",
        )
        for d in docs
    ]


@router.post("/knowledge-bases/{kb_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    kb_id: str,
    payload: DocumentUploadIn,
    db: AsyncSession = Depends(get_db),
    embedder: EmbeddingModel = Depends(get_embedder),
    llm: OpenAICompatProvider = Depends(get_llm),
    _: User = Depends(require_kb_access("edit")),
):
    """上传单篇文档（.md / .txt / .docx / .pdf）。

    Phase 3 T3 文档解析管线：先按原始字节存入对象存储（溯源/重解析），
    再按扩展名解析为纯文本，最后交给 ingestor 切分+向量化+进图。
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

    # 4) 摄入：切分 + 向量化 + ES 双写 + 知识图谱抽取（与 seed 摄入一致）
    ingester = DocumentIngester(embedder, es=ESClient(), graph=GraphStore(llm, embedder))
    doc = await ingester.ingest_text(
        kb_id, _extract_title(parsed.text, filename), parsed.text, db, object_key
    )

    return DocumentOut(
        id=str(doc.id),
        title=doc.title,
        type=_doc_type(filename),
        size_kb=round(len(raw) / 1024, 2),
        status=doc.status,
        updated_at=doc.updated_at.isoformat() if doc.updated_at else "",
    )


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
