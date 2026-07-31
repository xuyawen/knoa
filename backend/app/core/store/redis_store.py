import redis.asyncio as aioredis
from datetime import date, datetime, timedelta, timezone

_TTL = 60 * 60 * 24 * 30  # 30 天过期，避免每日 key 无限增长


def _normalize_question(question: str) -> str:
    """轻量归一化：去首尾空白 + 尾部标点，避免同一问题的输入差异碎片化计数。"""
    return question.strip().rstrip("？?！!。，,、；;…")


def _day_key(day: date, dept_id: str | None = None) -> str:
    """热搜 key：trending:{date}:{dept_id|global}。

    部门维度隔离：每个部门一个 sorted set，无部门用户计入 global 桶。
    展示侧按用户可见部门子树合并聚合，避免跨部门热搜泄漏。
    """
    return f"trending:{day.isoformat()}:{dept_id or 'global'}"


class RedisStore:
    def __init__(self, url: str):
        self.redis = aioredis.from_url(url, decode_responses=True)

    async def incr_trending(self, question: str, dept_id: str | None = None):
        """计数一次搜索/问答，归属到搜索者所在部门的桶（无部门 → global）。"""
        q = _normalize_question(question)
        if not q:
            return
        key = _day_key(datetime.now(timezone.utc).date(), dept_id)
        await self.redis.zincrby(key, 1, q)
        await self.redis.expire(key, _TTL)

    async def get_trending(self, limit: int = 10, dept_ids: frozenset[str] | None = None) -> list[tuple[str, int]]:
        """当日热搜 TopK（合并 dept_ids 可见桶 + global 桶）。"""
        return await self.get_trending_range(days=1, limit=limit, dept_ids=dept_ids)

    async def get_trending_range(
        self, days: int = 7, limit: int = 10, dept_ids: frozenset[str] | None = None,
    ) -> list[tuple[str, int]]:
        """近 N 天滑窗聚合：合并可见部门桶 + global 桶后降序取 TopK。

        dept_ids=None（超管）→ 合并当日全部桶；否则仅合并指定部门 + global。
        """
        today = datetime.now(timezone.utc).date()
        merged: dict[str, int] = {}
        for offset in range(days):
            day = today - timedelta(days=offset)
            keys = await self._day_keys(day, dept_ids)
            for key in keys:
                raw = await self.redis.zrevrange(key, 0, -1, withscores=True)
                for q, s in raw:
                    merged[q] = merged.get(q, 0) + int(s)
        ranked = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:limit]

    async def get_day_counts(self, day: date) -> list[tuple[str, int, str | None]]:
        """取指定日期的全量热搜计数，按部门分桶返回 (question, count, dept_id)（供 DB 落盘）。"""
        counts: list[tuple[str, int, str | None]] = []
        async for key in self.redis.scan_iter(match=f"trending:{day.isoformat()}:*", count=200):
            # key 形如 trending:2026-07-26:{dept_uuid|global}
            dept_part = key.rsplit(":", 1)[-1]
            dept_id = None if dept_part == "global" else dept_part
            raw = await self.redis.zrevrange(key, 0, -1, withscores=True)
            for q, s in raw:
                counts.append((q, int(s), dept_id))
        return counts

    async def _day_keys(self, day: date, dept_ids: frozenset[str] | None) -> list[str]:
        """当日需合并的 key 集合：global 桶始终包含；部门桶按可见性过滤。"""
        keys = [_day_key(day, None)]  # global 桶对所有人可见
        if dept_ids is None:
            # 超管：SCAN 当日全部桶
            async for key in self.redis.scan_iter(match=f"trending:{day.isoformat()}:*", count=200):
                if key not in keys:
                    keys.append(key)
        else:
            for d in dept_ids:
                keys.append(_day_key(day, d))
        return keys

    async def close(self):
        await self.redis.aclose()
