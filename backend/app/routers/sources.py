from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db import DocChunk, Document, KnowledgeBase
from app.deps import get_db
from app.models.knowledge import SourceDetailOut

router = APIRouter()


@router.get("/sources/{chunk_id}", response_model=SourceDetailOut)
async def get_source(chunk_id: str, db: AsyncSession = Depends(get_db)):
    """溯源详情：按 DocChunk 的 UUID 返回原文片段 + 文档标题 + 所属知识库。"""
    try:
        UUID(chunk_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="非法的 chunk id")

    chunk = await db.scalar(select(DocChunk).where(DocChunk.id == chunk_id))
    if chunk is None:
        raise HTTPException(status_code=404, detail="溯源不存在")

    doc = await db.scalar(select(Document).where(Document.id == chunk.document_id))
    kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == chunk.kb_id))

    return SourceDetailOut(
        id=str(chunk.id),
        title=doc.title if doc else "未知文档",
        kb=kb.name if kb else chunk.kb_id,
        content=chunk.content,
        chunk_index=chunk.chunk_index,
    )
