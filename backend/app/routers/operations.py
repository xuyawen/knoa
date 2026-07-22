"""Phase 1 业务统计：操作日志分页列表（审计 / 运营视图数据源）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import OperationLog
from app.deps import get_db
from app.models.operation_log import OperationLogOut
from app.core.security import require_roles

router = APIRouter()


@router.get("/operations")
async def list_operations(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_roles("admin")),
):
    """操作日志分页列表，按时间倒序。仅 admin 可见。"""
    total = await db.scalar(select(func.count()).select_from(OperationLog)) or 0
    rows = (
        await db.execute(
            select(OperationLog)
            .order_by(OperationLog.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()
    return {
        "items": [OperationLogOut.from_orm(r) for r in rows],
        "total": total,
        "page": page,
        "size": size,
    }
