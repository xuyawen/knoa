"""轻量进程内限流（单 worker 用）。

设计：按 (scope, user_id) 维度的滑动窗口计数。当前部署保持单 worker，
进程内字典即可；若以后扩到多 worker，应换 Redis 后端（slowapi + redis
storage）以保证配额跨进程一致。边缘洪水由 nginx `limit_req` 拦截，本模块
负责「按用户/按接口」的精细配额。
"""
from __future__ import annotations

import asyncio
import time

from fastapi import Depends, HTTPException

from app.core.security import get_current_user
from app.db import User

# key -> 命中时间戳列表（time.monotonic 秒）
_HITS: dict[str, list[float]] = {}
_LOCK = asyncio.Lock()


def rate_limit(times: int, seconds: int, scope: str):
    """返回一个 FastAPI 依赖：限制每个用户在 seconds 窗口内最多 times 次。

    超限抛出 429 并带 Retry-After 头，前端可据此提示「操作过于频繁」。
    """

    async def _dep(user: User = Depends(get_current_user)) -> None:
        key = f"{scope}:{user.id}"
        now = time.monotonic()
        async with _LOCK:
            hits = _HITS.get(key)
            if hits is None:
                hits = []
                _HITS[key] = hits
            # 丢弃窗口外的旧时间戳
            hits[:] = [t for t in hits if now - t < seconds]
            if len(hits) >= times:
                retry_after = max(1, int(seconds - (now - hits[0])))
                raise HTTPException(
                    status_code=429,
                    detail=f"操作过于频繁，请在 {retry_after} 秒后重试",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)
            # 窗口内已无命中则清理 key，避免字典随用户数无限增长
            if not hits:
                _HITS.pop(key, None)

    return _dep
