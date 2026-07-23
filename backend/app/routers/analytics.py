"""Phase 1 业务统计：Dashboard 指标 / 趋势 / 文档分类占比。"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
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


async def _count(
    db: AsyncSession,
    model,
    col,
    start: datetime,
    end: datetime,
    action: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(model).where(col >= start, col < end)
    if action is not None:
        stmt = stmt.where(OperationLog.action == action)
    return await db.scalar(stmt) or 0


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
    # 问答（对话页）与搜索（智能搜索页）是两条独立埋点，分别统计
    ai_answers = await _count(db, OperationLog, OperationLog.created_at, t_start, t_end, action="ask")
    user_searches = await _count(db, OperationLog, OperationLog.created_at, t_start, t_end, action="search")
    active_users = await _distinct_users(db, t_start)

    y_new = await _count(db, Document, Document.created_at, y_start, y_end)
    y_ai = await _count(db, OperationLog, OperationLog.created_at, y_start, y_end, action="ask")
    y_search = await _count(db, OperationLog, OperationLog.created_at, y_start, y_end, action="search")
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
            "userSearches": pct(user_searches, y_search),
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
        ask_cnt = await db.scalar(
            select(func.count()).select_from(OperationLog).where(
                OperationLog.action == "ask",
                OperationLog.created_at >= b_start,
                OperationLog.created_at < b_end,
            )
        ) or 0
        search_cnt = await db.scalar(
            select(func.count()).select_from(OperationLog).where(
                OperationLog.action == "search",
                OperationLog.created_at >= b_start,
                OperationLog.created_at < b_end,
            )
        ) or 0
        points.append({"date": label, "aiAnswers": ask_cnt, "searches": search_cnt})
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
    """文档统计：按 category / status / type 聚合 + 近7天新增趋势（文档统计分区真实数据源）。"""
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
    # 文档类型从 source_path 扩展名推断（与 knowledge.py _doc_type 对齐）
    type_expr = case(
        (Document.source_path.ilike("%.pdf"), "PDF"),
        (Document.source_path.ilike("%.docx"), "DOCX"),
        (Document.source_path.ilike("%.md"), "MD"),
        (Document.source_path.ilike("%.txt"), "TXT"),
        else_="其他",
    )
    by_type = (await db.execute(
        select(type_expr, func.count()).group_by(type_expr).order_by(func.count().desc())
    )).all()
    total = await db.scalar(select(func.count()).select_from(Document)) or 0

    # 近7天新增文档趋势（按本地日期）
    now = datetime.now(timezone.utc)
    recent_trend: list[dict] = []
    for i in range(7):
        day_start = (now - timedelta(days=6 - i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        cnt = await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.created_at >= day_start, Document.created_at < day_end)
        ) or 0
        recent_trend.append({"date": day_start.astimezone().strftime("%m-%d"), "count": cnt})

    return {
        "total": total,
        "byCategory": [{"category": (r[0] or "未分类"), "count": r[1]} for r in by_cat],
        "byStatus": [{"status": (r[0] or "未知"), "count": r[1]} for r in by_status],
        "byType": [{"type": r[0], "count": r[1]} for r in by_type],
        "recentTrend": recent_trend,
    }
