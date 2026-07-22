"""Phase 1 业务统计：操作日志分页列表（审计 / 运营视图数据源）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import paginate
from app.db import OperationLog
from app.deps import get_db
from app.models.common import PaginatedOut
from app.models.operation_log import OperationLogOut
from app.core.security import require_roles

router = APIRouter()


@router.get("/operations", response_model=PaginatedOut[OperationLogOut])
async def list_operations(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_roles("admin")),
):
    """操作日志分页列表，按时间倒序。仅 admin 可见。"""
    stmt = select(OperationLog).order_by(OperationLog.created_at.desc())
    rows, total = await paginate(db, stmt, page=page, page_size=size)
    pages = max(1, (total + size - 1) // size) if total else 1
    return {
        "items": [OperationLogOut.from_orm(r[0]) for r in rows],
        "total": total,
        "page": page,
        "page_size": size,
        "pages": pages,
    }
