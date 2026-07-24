from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.security import get_current_user, get_kb_permission_level
from app.db import DocChunk, Document, KnowledgeBase, User
from app.deps import get_db
from app.models.knowledge import SourceDetailOut

router = APIRouter()


@router.get("/sources/{chunk_id}", response_model=SourceDetailOut)
async def get_source(
    chunk_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """溯源详情：按 DocChunk 的 UUID 返回原文片段 + 文档标题 + 所属知识库。

    需登录，且当前用户必须对该 chunk 所属 KB 有 view+ 权限，
    防止凭借任意 chunk UUID 读取其无权查看的文档全文（P0-1a）。
    """
    try:
        UUID(chunk_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="非法的 chunk id") from None

    chunk = await db.scalar(select(DocChunk).where(DocChunk.id == chunk_id))
    if chunk is None:
        raise HTTPException(status_code=404, detail="溯源不存在")

    # 库级权限校验：开放库（无任何权限记录）对全体已登录用户可见，
    # 严格隔离库则要求当前用户有 view+ 权限，否则 403。
    level = await get_kb_permission_level(db, chunk.kb_id, user)
    if level is None:
        raise HTTPException(status_code=403, detail="无权访问该溯源内容")

    doc = await db.scalar(select(Document).where(Document.id == chunk.document_id))
    kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == chunk.kb_id))

    return SourceDetailOut(
        id=str(chunk.id),
        title=doc.title if doc else "未知文档",
        kb=kb.name if kb else chunk.kb_id,
        content=chunk.content,
        chunk_index=chunk.chunk_index,
    )
