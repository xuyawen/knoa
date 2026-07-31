"""LLM 调用日志 Pydantic 模型 + fire-and-forget 落库 helper。

调用日志页「模型调用」tab 的数据来源：LLM 三个调用面（stream_chat/chat/tool_call）
在出口处经 capture_llm_call 异步写入 llm_call 表。写入走独立后台任务 + 独立 session，
best-effort：任何失败只告警不抛、绝不阻塞 LLM 响应与主请求。机制与 errors.py 同源。
"""
import asyncio
import contextvars
import logging
import time
from collections import deque

from app.core.logging_config import request_id_var
from app.db import LLMCall
from app.models.knowledge import CamelModel

logger = logging.getLogger("knoa.llm_calls")

# 保留策略：超期 / 超量在每次写入时顺手清理，控制表膨胀（无需额外定时任务）
RETENTION_DAYS = 14
MAX_ROWS = 20000

# 写入限流（best-effort）：异常高频调用时削峰，避免把数据库写挂；正常量级远低于此
_MAX_WRITES_PER_SEC = 50
_recent_writes: deque[float] = deque()

# 调用方标签：由具体业务路径 set（如 graph.py 抽图设 "graph_extract"），
# capture 时读取写入 caller 列；未设置则为 None，页面以 request_type 区分。
caller_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "llm_caller", default=None
)


class LLMCallOut(CamelModel):
    id: str
    model: str
    requestType: str
    caller: str | None = None
    status: str
    latencyMs: int | None = None
    tokensIn: int | None = None
    tokensOut: int | None = None
    error: str | None = None
    preview: str | None = None
    rid: str | None = None
    createdAt: str

    @classmethod
    def from_orm(cls, c: "LLMCall") -> "LLMCallOut":
        return cls(
            id=str(c.id),
            model=c.model,
            requestType=c.request_type,
            caller=c.caller,
            status=c.status,
            latencyMs=c.latency_ms,
            tokensIn=c.tokens_in,
            tokensOut=c.tokens_out,
            error=c.error,
            preview=c.preview,
            rid=c.rid,
            createdAt=c.created_at.isoformat() if c.created_at else "",
        )


def capture_llm_call(
    *,
    model: str,
    request_type: str,
    status: str,
    latency_ms: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    error: str | None = None,
    preview: str | None = None,
) -> None:
    """fire-and-forget 记录一条 LLM 调用（同步调用，内部派生后台任务异步落库）。

    必须在事件循环内调用（LLM 调用均在异步上下文，满足）。caller 从 caller_var
    取、rid 与后端日志 [rid=] 同源（默认 "-" 视为无请求上下文，落 None）。限流
    命中或无事件循环时静默跳过——调用日志是辅助能力，绝不允许影响业务。
    preview 统一截断 200 字（列宽 500 留余量），不存完整 prompt/response。
    """
    now = time.monotonic()
    while _recent_writes and now - _recent_writes[0] > 1.0:
        _recent_writes.popleft()
    if len(_recent_writes) >= _MAX_WRITES_PER_SEC:
        return  # 削峰：宁可丢少量调用记录，也不拖垮数据库
    _recent_writes.append(now)

    caller = caller_var.get()
    rid = request_id_var.get()
    try:
        task = asyncio.get_running_loop().create_task(
            _persist(
                model=model[:100],
                request_type=request_type[:32],
                caller=(caller[:64] if caller else None),
                status=status[:16],
                latency_ms=latency_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                error=error,
                preview=(preview[:200] if preview else None),
                rid=(rid if rid and rid != "-" else None),
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
            db.add(LLMCall(**fields))
            # 保留策略：先删超期，再削超量（按最旧优先），cutoff 在 Python 端算
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
            await db.execute(
                delete(LLMCall).where(LLMCall.created_at < cutoff_dt)
            )
            total = await db.scalar(select(func.count()).select_from(LLMCall)) or 0
            if total > MAX_ROWS:
                cutoff = await db.scalar(
                    select(LLMCall.created_at)
                    .order_by(LLMCall.created_at.desc())
                    .offset(MAX_ROWS - 1)
                    .limit(1)
                )
                if cutoff is not None:
                    await db.execute(delete(LLMCall).where(LLMCall.created_at < cutoff))
            await db.commit()
    except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort 落库，失败不抛)
        logger.warning("capture_llm_call persist failed: %s", e)
