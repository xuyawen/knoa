import redis.asyncio as aioredis
from datetime import date, datetime, timedelta, timezone


def _normalize_question(question: str) -> str:
    """轻量归一化：去首尾空白 + 尾部标点，避免同一问题的输入差异碎片化计数。"""
    return question.strip().rstrip("？?！!。，,、；;…")


class RedisStore:
    def __init__(self, url: str):
        self.redis = aioredis.from_url(url, decode_responses=True)

    async def incr_trending(self, question: str):
        q = _normalize_question(question)
        if not q:
            return
        key = f"trending:{datetime.now(timezone.utc).date().isoformat()}"
        await self.redis.zincrby(key, 1, q)
        # 写入即设过期（30 天），避免每日 key 无限增长
        await self.redis.expire(key, 60 * 60 * 24 * 30)

    async def get_trending(self, limit: int = 10) -> list[tuple[str, int]]:
        key = f"trending:{datetime.now(timezone.utc).date().isoformat()}"
        raw = await self.redis.zrevrange(key, 0, limit - 1, withscores=True)
        return [(q, int(s)) for q, s in raw]

    async def get_trending_range(self, days: int = 7, limit: int = 10) -> list[tuple[str, int]]:
        """近 N 天滑窗聚合：合并各日 key 下同一问题的计数后降序取 TopK。"""
        today = datetime.now(timezone.utc).date()
        merged: dict[str, int] = {}
        for offset in range(days):
            key = f"trending:{(today - timedelta(days=offset)).isoformat()}"
            raw = await self.redis.zrevrange(key, 0, -1, withscores=True)
            for q, s in raw:
                merged[q] = merged.get(q, 0) + int(s)
        ranked = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:limit]

    async def get_day_counts(self, day: date) -> list[tuple[str, int]]:
        """取指定日期的全量热搜计数（供 DB 落盘）。"""
        key = f"trending:{day.isoformat()}"
        raw = await self.redis.zrevrange(key, 0, -1, withscores=True)
        return [(q, int(s)) for q, s in raw]

    async def close(self):
        await self.redis.aclose()
