"""架构图6 文档处理任务 API（前端轮询进度条）。

列表按当前用户可见 KB 范围过滤（admin 看全部）；支持按 document_id / kb_id 过滤。
"""
import uuid
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import paginate
from app.core.security import get_accessible_kb_ids, get_current_user
from app.db import Document, DocumentTask
from app.deps import get_db
from app.models.common import PaginatedOut
from app.models.knowledge import DocumentTaskOut

router = APIRouter()


def _task_out(t: DocumentTask, title: str | None = None) -> DocumentTaskOut:
    return DocumentTaskOut(
        id=str(t.id),
        document_id=str(t.document_id) if t.document_id else None,
        kb_id=t.kb_id,
        filename=t.filename,
        status=t.status,
        progress=t.progress,
        current_step=t.current_step,
        error_message=t.error_message,
        started_at=t.started_at.isoformat() if t.started_at else None,
        completed_at=t.completed_at.isoformat() if t.completed_at else None,
        created_at=t.created_at.isoformat() if t.created_at else "",
        document_title=title,
    )


@router.get("/documents/tasks", response_model=PaginatedOut[DocumentTaskOut])
async def list_tasks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    document_id: str | None = Query(default=None),
    kb_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    allowed = set(await get_accessible_kb_ids(db, user))
    # 非 admin 且无任何可见 KB 时直接返回空分页
    if user.role != "admin" and not allowed:
        return {"items": [], "total": 0, "page": page, "page_size": size, "pages": 1}

    stmt = select(DocumentTask, Document.title).outerjoin(
        Document, Document.id == DocumentTask.document_id
    )
    if document_id:
        try:
            stmt = stmt.where(DocumentTask.document_id == uuid.UUID(document_id))
        except Exception:
            raise HTTPException(status_code=400, detail="document_id 非法")
    if kb_id:
        stmt = stmt.where(DocumentTask.kb_id == kb_id)
    if user.role != "admin":
        stmt = stmt.where(DocumentTask.kb_id.in_(allowed))
    stmt = stmt.order_by(DocumentTask.created_at.desc())

    rows, total = await paginate(db, stmt, page=page, page_size=size)
    out = [_task_out(t, title) for t, title in rows]
    pages = max(1, ceil(total / size)) if total else 1
    return {
        "items": out,
        "total": total,
        "page": page,
        "page_size": size,
        "pages": pages,
    }


@router.get("/documents/tasks/{task_id}", response_model=DocumentTaskOut)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        tid = uuid.UUID(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="task_id 非法")
    row = (
        await db.execute(
            select(DocumentTask, Document.title)
            .outerjoin(Document, Document.id == DocumentTask.document_id)
            .where(DocumentTask.id == tid)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    t, title = row
    if user.role != "admin":
        allowed = set(await get_accessible_kb_ids(db, user))
        if t.kb_id not in allowed:
            raise HTTPException(status_code=403, detail="无权查看该任务")
    return _task_out(t, title)
