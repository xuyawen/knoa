"""系统事件 Pydantic 模型 + fire-and-forget 落库 helper。

系统事件页的数据源：后端全量 API 请求（observability 中间件，2xx/3xx/4xx/5xx）
与前端上报（/api/events）都通过 capture_error 异步写入 error_event 表。
写入走独立后台任务 + 独立 session，best-effort：任何失败只告警不抛、
绝不阻塞主请求。
"""
import asyncio
import logging
import time
from collections import deque

from app.db import ErrorEvent
from app.models.knowledge import CamelModel

logger = logging.getLogger("knoa.errors")

# 保留策略：超期 / 超量在每次写入时顺手清理，控制表膨胀（无需额外定时任务）
RETENTION_DAYS = 14
MAX_ROWS = 50000  # 全量请求日志量级较之前 4xx/5xx 放大 ~10 倍，相应放宽上限

# 写入限流（best-effort）：错误风暴时削峰，避免把数据库写挂；正常量级远低于此
_MAX_WRITES_PER_SEC = 50
_recent_writes: deque[float] = deque()


class ErrorEventOut(CamelModel):
    id: str
    source: str
    level: str
    method: str | None = None
    path: str | None = None
    statusCode: int | None = None
    rid: str | None = None
    etype: str | None = None
    message: str | None = None
    stack: str | None = None
    ip: str | None = None
    userAgent: str | None = None
    url: str | None = None
    requestBody: str | None = None
    createdAt: str

    @classmethod
    def from_orm(cls, e: "ErrorEvent") -> "ErrorEventOut":
        return cls(
            id=str(e.id),
            source=e.source,
            level=e.level,
            method=e.method,
            path=e.path,
            statusCode=e.status_code,
            rid=e.rid,
            etype=e.etype,
            message=e.message,
            stack=e.stack,
            ip=e.ip,
            userAgent=e.user_agent,
            url=e.url,
            requestBody=e.request_body,
            createdAt=e.created_at.isoformat() if e.created_at else "",
        )


def capture_error(
    *,
    source: str,
    level: str = "error",
    method: str | None = None,
    path: str | None = None,
    status_code: int | None = None,
    rid: str | None = None,
    etype: str | None = None,
    message: str | None = None,
    stack: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    url: str | None = None,
    request_body: str | None = None,
) -> None:
    """fire-and-forget 记录一条错误事件（同步调用，内部派生后台任务异步落库）。

    必须在事件循环内调用（中间件 / 异步端点均满足）。限流命中或无事件循环时
    静默跳过——错误记录是辅助能力，绝不允许影响业务。
    """
    now = time.monotonic()
    while _recent_writes and now - _recent_writes[0] > 1.0:
        _recent_writes.popleft()
    if len(_recent_writes) >= _MAX_WRITES_PER_SEC:
        return  # 错误风暴削峰：宁可丢少量错误记录，也不拖垮数据库
    _recent_writes.append(now)
    try:
        task = asyncio.get_running_loop().create_task(
            _persist(
                source=source, level=level, method=method, path=path,
                status_code=status_code, rid=rid, etype=etype, message=message,
                stack=stack, ip=ip, user_agent=user_agent, url=url,
                request_body=request_body,
            )
        )
        _BG_TASKS.add(task)
        task.add_done_callback(_BG_TASKS.discard)
    except RuntimeError:
        pass  # 无运行中的事件循环（理论上不会发生），跳过


# 持有后台任务强引用，防止被 GC 提前回收（asyncio 只持弱引用）
_BG_TASKS: set[asyncio.Task] = set()


async def _persist(**fields) -> None:
    """独立 session 写入 + 顺手按保留策略清理；best-effort，失败仅告警。"""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import delete, func, select

    from app.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            db.add(ErrorEvent(**fields))
            # 保留策略：先删超期，再削超量（按最旧优先）
            # cutoff 在 Python 端算（避开 func.make_interval 的方言/关键字参数坑，更可移植）
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
            await db.execute(
                delete(ErrorEvent).where(ErrorEvent.created_at < cutoff_dt)
            )
            total = await db.scalar(select(func.count()).select_from(ErrorEvent)) or 0
            if total > MAX_ROWS:
                cutoff = await db.scalar(
                    select(ErrorEvent.created_at)
                    .order_by(ErrorEvent.created_at.desc())
                    .offset(MAX_ROWS - 1)
                    .limit(1)
                )
                if cutoff is not None:
                    await db.execute(delete(ErrorEvent).where(ErrorEvent.created_at < cutoff))
            await db.commit()
    except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort 落库，失败不抛)
        logger.warning("capture_error persist failed: %s", e)
