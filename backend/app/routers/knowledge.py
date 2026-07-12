from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.ingestor import DocumentIngester
from app.db import DocChunk, Document, KnowledgeBase
from app.deps import get_db, get_embedder
from app.models.knowledge import (
    DocumentOut,
    DocumentUploadIn,
    HealthItemOut,
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
async def get_knowledge_bases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at))
    kbs = result.scalars().all()

    kb_list = []
    health_list = []
    for kb in kbs:
        doc_count = await db.scalar(
            select(func.count(Document.id)).where(Document.kb_id == kb.id)
        )
        latest = await db.scalar(
            select(func.max(Document.updated_at)).where(Document.kb_id == kb.id)
        )

        badge = None
        badge_type = None
        if kb.pending_count > 0:
            badge = f"{kb.pending_count} 份待复核"
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


@router.get("/knowledge-bases/{kb_id}/documents", response_model=list[DocumentOut])
async def list_documents(kb_id: str, db: AsyncSession = Depends(get_db)):
    """列出某知识库下的文档。"""
    result = await db.execute(
        select(Document).where(Document.kb_id == kb_id).order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        DocumentOut(
            id=str(d.id),
            title=d.title,
            type="MD" if d.source_path.endswith((".md", ".markdown")) else "TXT",
            size_kb=round(len(d.content_md.encode("utf-8", errors="ignore")) / 1024, 2),
            status="待复核",
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
):
    """上传单篇文档（.md / .txt）。前端用 FileReader 读文本后以 JSON 提交，避免 multipart 依赖。"""
    kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    filename = payload.filename or "untitled"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("md", "markdown"):
        ftype = "MD"
    elif ext == "txt":
        ftype = "TXT"
    else:
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件格式 .{ext or '未知'}，当前仅支持 .md / .txt（PDF 解析将在后续阶段支持）",
        )

    ingester = DocumentIngester(embedder)
    doc = await ingester.ingest_text(
        kb_id, _extract_title(payload.content, filename), payload.content, db, filename
    )

    return DocumentOut(
        id=str(doc.id),
        title=doc.title,
        type=ftype,
        size_kb=round(len(payload.content.encode("utf-8", errors="ignore")) / 1024, 2),
        status="待复核",
        updated_at=doc.updated_at.isoformat() if doc.updated_at else "",
    )


def _extract_title(content: str, fallback: str) -> str:
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback
