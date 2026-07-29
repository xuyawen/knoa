from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Trending, User
from app.deps import get_db, get_redis
from app.models.knowledge import TrendingItemOut
from app.core.security import get_current_user
from redis.exceptions import RedisError

router = APIRouter()


@router.get("/trending", response_model=list[TrendingItemOut])
async def get_trending(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """热门搜索榜：近 7 天滑窗聚合（搜索与问答均计数）。

    数据源优先级：Redis 各日 key 合并 → DB 近 7 天 SUM → DB 全量（冷启动兜底）。
    """
    redis = get_redis()
    try:
        raw = await redis.get_trending_range(days=7, limit=10)
        if raw:
            return [TrendingItemOut(question=q, count=c) for q, c in raw]
    except RedisError:
        pass  # ponytail: Redis 不可用时静默回退 DB

    # 回退到 DB：近 7 天按问题聚合
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=6)
    result = await db.execute(
        select(Trending.question, func.sum(Trending.count).label("total"))
        .where(Trending.date >= cutoff)
        .group_by(Trending.question)
        .order_by(func.sum(Trending.count).desc())
        .limit(10)
    )
    rows = result.all()
    if not rows:
        # 冷启动兜底：近 7 天无任何落盘数据时用全历史（种子数据）
        result = await db.execute(
            select(Trending.question, func.sum(Trending.count).label("total"))
            .group_by(Trending.question)
            .order_by(func.sum(Trending.count).desc())
            .limit(10)
        )
        rows = result.all()
    return [TrendingItemOut(question=r.question, count=int(r.total)) for r in rows]
