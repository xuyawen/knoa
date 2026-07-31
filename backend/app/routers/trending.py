from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Trending, User
from app.deps import get_db, get_redis
from app.models.knowledge import TrendingItemOut
from app.core.security import compute_visible_dept_ids, get_current_user, is_super_admin
from redis.exceptions import RedisError

router = APIRouter()


@router.get("/trending", response_model=list[TrendingItemOut])
async def get_trending(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """热门搜索榜：近 7 天滑窗聚合（搜索与问答均计数），按部门可见性过滤。

    超管看全量；普通用户仅看自己可见部门子树 + 全局桶（无部门用户贡献）。
    数据源优先级：Redis 各日 key 合并 → DB 近 7 天 SUM → DB 全量（冷启动兜底）。
    """
    # 部门可见性：超管 → None（合并全部桶）；普通用户 → 可见部门 id 集合
    dept_ids: frozenset[str] | None = None
    if not await is_super_admin(db, user):
        dept_ids = await compute_visible_dept_ids(db, user)

    redis = get_redis()
    try:
        raw = await redis.get_trending_range(days=7, limit=10, dept_ids=dept_ids)
        if raw:
            return [TrendingItemOut(question=q, count=c) for q, c in raw]
    except RedisError:
        pass  # ponytail: Redis 不可用时静默回退 DB

    # 回退到 DB：近 7 天按问题聚合（同样应用部门过滤）
    dept_clause = None
    if dept_ids is not None:
        uuids = [UUID(d) for d in dept_ids]
        dept_clause = or_(
            Trending.department_id.is_(None),
            Trending.department_id.in_(uuids),
        )

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=6)
    stmt = (
        select(Trending.question, func.sum(Trending.count).label("total"))
        .where(Trending.date >= cutoff)
        .group_by(Trending.question)
        .order_by(func.sum(Trending.count).desc())
        .limit(10)
    )
    if dept_clause is not None:
        stmt = stmt.where(dept_clause)
    rows = (await db.execute(stmt)).all()
    if not rows:
        # 冷启动兜底：近 7 天无任何落盘数据时用全历史（种子数据）
        stmt = (
            select(Trending.question, func.sum(Trending.count).label("total"))
            .group_by(Trending.question)
            .order_by(func.sum(Trending.count).desc())
            .limit(10)
        )
        if dept_clause is not None:
            stmt = stmt.where(dept_clause)
        rows = (await db.execute(stmt)).all()
    return [TrendingItemOut(question=r.question, count=int(r.total)) for r in rows]
