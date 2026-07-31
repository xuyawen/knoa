"""调用日志 API：LLM 调用记录查询 / 清空（仅用户管理员可见）。

数据源是 llm_call 表，由 capture_llm_call 从 LLM 三个调用面（stream_chat/chat/
tool_call）异步写入。本路由只读 + 清空，不落业务库。与 errors.py 同款门控。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, or_, select

from app.core.pagination import paginate
from app.core.rbac import Perm
from app.core.security import require_permission
from app.db import LLMCall, User
from app.deps import get_db
from app.models.common import PaginatedOut
from app.models.llm_calls import LLMCallOut

router = APIRouter()


@router.get("/llm-calls", response_model=PaginatedOut[LLMCallOut])
async def list_llm_calls(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    request_type: str | None = None,
    status: str | None = None,
    model: str | None = None,
    caller: str | None = None,
    rid: str | None = None,
    q: str | None = None,
    db=Depends(get_db),
    _: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    """LLM 调用分页列表（按时间倒序）。

    过滤维度：request_type（stream_chat/chat/tool_call）/ status（success/error）/
    model（精确）/ caller（调用方）/ rid（请求 id）/ q（model/error/preview 模糊）。
    返回统一分页结构。
    """
    base = select(LLMCall)
    if request_type:
        base = base.where(LLMCall.request_type == request_type)
    if status:
        base = base.where(LLMCall.status == status)
    if model:
        base = base.where(LLMCall.model == model)
    if caller:
        base = base.where(LLMCall.caller == caller)
    if rid:
        base = base.where(LLMCall.rid == rid)
    if q:
        like = f"%{q}%"
        base = base.where(
            or_(
                LLMCall.model.ilike(like),
                LLMCall.error.ilike(like),
                LLMCall.preview.ilike(like),
            )
        )
    stmt = base.order_by(LLMCall.created_at.desc())
    rows, total = await paginate(db, stmt, page=page, page_size=size)
    pages = max(1, (total + size - 1) // size) if total else 1
    return {
        "items": [LLMCallOut.from_orm(r[0]) for r in rows],
        "total": total,
        "page": page,
        "page_size": size,
        "pages": pages,
    }


@router.delete("/llm-calls", status_code=204)
async def clear_llm_calls(
    db=Depends(get_db),
    _: User = Depends(require_permission(Perm.USER_MANAGE)),
):
    """清空 LLM 调用记录。"""
    await db.execute(delete(LLMCall))
    await db.commit()
