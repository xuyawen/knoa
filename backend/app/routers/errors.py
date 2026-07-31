"""错误管理 API：错误事件查询 / 清空（仅用户管理员可见）。

数据源是 error_event 表，由 capture_error 从两处异步写入：后端 HTTP 4xx/5xx
（observability 中间件）与前端上报（/api/events）。本路由只读 + 清空，不落业务库。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, or_, select

from app.core.pagination import paginate
from app.core.rbac import Perm
from app.core.security import require_permission
from app.db import ErrorEvent, User
from app.deps import get_db
from app.models.common import PaginatedOut
from app.models.errors import ErrorEventOut

router = APIRouter()


@router.get("/errors", response_model=PaginatedOut[ErrorEventOut])
async def list_errors(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    source: str | None = None,
    level: str | None = None,
    status_code: int | None = Query(None, alias="status"),
    etype: str | None = None,
    q: str | None = None,
    db=Depends(get_db),
    _: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    """错误事件分页列表（按时间倒序）。

    过滤维度：source（backend/frontend）/ level（info/warn/error）/ status（状态码）/
    etype（事件类型）/ q（path/message 模糊）。返回统一分页结构。
    """
    base = select(ErrorEvent)
    if source:
        base = base.where(ErrorEvent.source == source)
    if level:
        base = base.where(ErrorEvent.level == level)
    if status_code is not None:
        base = base.where(ErrorEvent.status_code == status_code)
    if etype:
        base = base.where(ErrorEvent.etype == etype)
    if q:
        like = f"%{q}%"
        base = base.where(or_(ErrorEvent.path.ilike(like), ErrorEvent.message.ilike(like)))
    stmt = base.order_by(ErrorEvent.created_at.desc())
    rows, total = await paginate(db, stmt, page=page, page_size=size)
    pages = max(1, (total + size - 1) // size) if total else 1
    return {
        "items": [ErrorEventOut.from_orm(r[0]) for r in rows],
        "total": total,
        "page": page,
        "page_size": size,
        "pages": pages,
    }


@router.delete("/errors", status_code=204)
async def clear_errors(
    source: str | None = None,
    db=Depends(get_db),
    _: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    """清空错误事件（可按 source 只清后端 / 前端）。"""
    stmt = delete(ErrorEvent)
    if source:
        stmt = stmt.where(ErrorEvent.source == source)
    await db.execute(stmt)
    await db.commit()
