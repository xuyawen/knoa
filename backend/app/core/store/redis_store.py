import redis.asyncio as aioredis
from datetime import date


class RedisStore:
    def __init__(self, url: str):
        self.redis = aioredis.from_url(url, decode_responses=True)

    async def incr_trending(self, question: str):
        key = f"trending:{date.today().isoformat()}"
        await self.redis.zincrby(key, 1, question)
        # 写入即设过期（30 天），避免每日 key 无限增长
        await self.redis.expire(key, 60 * 60 * 24 * 30)

    async def get_trending(self, limit: int = 10) -> list[tuple[str, int]]:
        key = f"trending:{date.today().isoformat()}"
        raw = await self.redis.zrevrange(key, 0, limit - 1, withscores=True)
        return [(q, int(s)) for q, s in raw]

    async def close(self):
        await self.redis.aclose()
