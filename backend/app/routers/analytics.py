"""Phase 1 业务统计：Dashboard 指标 / 趋势 / 文档分类占比。"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, OperationLog, User
from app.deps import get_db
from app.core.security import get_current_user

router = APIRouter()


def _today_range() -> "tuple[datetime, datetime]":
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


def _yesterday_range() -> "tuple[datetime, datetime]":
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, end


async def _count(db: AsyncSession, model, col, start: datetime, end: datetime) -> int:
    return await db.scalar(
        select(func.count()).select_from(model).where(col >= start, col < end)
    ) or 0


async def _distinct_users(db: AsyncSession, start: datetime, end: datetime | None = None) -> int:
    stmt = select(func.count(func.distinct(OperationLog.user_id))).select_from(OperationLog).where(
        OperationLog.user_id.isnot(None), OperationLog.created_at >= start
    )
    if end is not None:
        stmt = stmt.where(OperationLog.created_at < end)
    return await db.scalar(stmt) or 0


@router.get("/analytics/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    t_start, t_end = _today_range()
    y_start, y_end = _yesterday_range()

    total_docs = await db.scalar(select(func.count()).select_from(Document)) or 0
    today_new = await _count(db, Document, Document.created_at, t_start, t_end)
    # 当前系统只有一个问答入口 /api/ask（Search 页也走它），
    # 故「AI 问答」与「用户搜索」同源，均取自 OperationLog action='ask'。
    ai_answers = await _count(db, OperationLog, OperationLog.created_at, t_start, t_end)
    user_searches = ai_answers
    active_users = await _distinct_users(db, t_start)

    y_new = await _count(db, Document, Document.created_at, y_start, y_end)
    y_ai = await _count(db, OperationLog, OperationLog.created_at, y_start, y_end)
    y_active = await _distinct_users(db, y_start, y_end)

    def pct(cur: int, prev: int) -> float:
        if prev <= 0:
            return 100.0 if cur > 0 else 0.0
        return round((cur - prev) / prev * 100, 1)

    return {
        "totalDocs": total_docs,
        "todayNewDocs": today_new,
        "aiAnswers": ai_answers,
        "userSearches": user_searches,
        "activeUsers": active_users,
        "deltas": {
            # 累计总数无昨日环比，给 0；其余给真实日环比
            "totalDocs": 0.0,
            "todayNewDocs": pct(today_new, y_new),
            "aiAnswers": pct(ai_answers, y_ai),
            "userSearches": pct(user_searches, y_ai),
            "activeUsers": pct(active_users, y_active),
        },
    }


@router.get("/analytics/trend")
async def trend(
    period: str = Query("week", alias="range", pattern="^(today|week|month)$"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """按时间桶聚合问答次数（真实数据源：OperationLog.action='ask'）。"""
    now = datetime.now(timezone.utc)
    if period == "today":
        buckets, step, fmt = 24, timedelta(hours=1), "%H:00"
        start = now - timedelta(hours=23)
    elif period == "month":
        buckets, step, fmt = 30, timedelta(days=1), "%m-%d"
        start = now - timedelta(days=29)
    else:  # week
        buckets, step, fmt = 7, timedelta(days=1), "%m-%d"
        start = now - timedelta(days=6)

    labels: list[str] = []
    points: list[dict] = []
    for i in range(buckets):
        b_start = start + step * i
        b_end = b_start + step
        label = b_start.astimezone().strftime(fmt)
        labels.append(label)
        cnt = await db.scalar(
            select(func.count()).select_from(OperationLog).where(
                OperationLog.action == "ask",
                OperationLog.created_at >= b_start,
                OperationLog.created_at < b_end,
            )
        ) or 0
        points.append({"date": label, "aiAnswers": cnt, "searches": cnt})
    return {"range": period, "labels": labels, "points": points}


@router.get("/analytics/doc-category")
async def doc_category(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """按 category 分组统计文档数（饼图数据源，替代前端硬编码饼图）。"""
    rows = (await db.execute(
        select(Document.category, func.count())
        .group_by(Document.category)
        .order_by(func.count().desc())
    )).all()
    return [{"category": (r[0] or "未分类"), "count": r[1]} for r in rows]


@router.get("/analytics/doc-stats")
async def doc_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """文档统计：按 category / status 聚合（文档统计分区真实数据源）。"""
    by_cat = (await db.execute(
        select(Document.category, func.count())
        .group_by(Document.category)
        .order_by(func.count().desc())
    )).all()
    by_status = (await db.execute(
        select(Document.status, func.count())
        .group_by(Document.status)
        .order_by(func.count().desc())
    )).all()
    total = await db.scalar(select(func.count()).select_from(Document)) or 0
    return {
        "total": total,
        "byCategory": [{"category": (r[0] or "未分类"), "count": r[1]} for r in by_cat],
        "byStatus": [{"status": (r[0] or "未知"), "count": r[1]} for r in by_status],
    }
