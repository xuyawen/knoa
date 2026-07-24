from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Trending
from app.deps import get_db, get_redis
from app.models.knowledge import TrendingItemOut
from redis.exceptions import RedisError

router = APIRouter()


@router.get("/trending", response_model=list[TrendingItemOut])
async def get_trending(db: AsyncSession = Depends(get_db)):  # noqa: B008  (FastAPI 鉴权依赖惯用法)
    # 优先从 Redis sorted set 读今日实时数据
    redis = get_redis()
    try:
        raw = await redis.get_trending(10)
        if raw:
            return [TrendingItemOut(question=q, count=c) for q, c in raw]
    except RedisError:
        pass  # ponytail: Redis 不可用时静默回退 DB

    # 回退到 DB 种子数据
    result = await db.execute(
        select(Trending)
        .where(Trending.date == datetime.now(timezone.utc).date())
        .order_by(Trending.count.desc())
        .limit(10)
    )
    rows = result.scalars().all()
    if not rows:
        result = await db.execute(
            select(Trending).order_by(Trending.count.desc()).limit(10)
        )
        rows = result.scalars().all()
    return [TrendingItemOut(question=r.question, count=r.count) for r in rows]
