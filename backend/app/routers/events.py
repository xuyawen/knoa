"""前端可观测上报端点（零依赖）。

前端 monitor.ts 通过 sendBeacon/fetch 把浏览器内的错误、未捕获 Promise
拒绝、首屏性能埋点发到这里。后端只做两件事：结构化日志（进独立的
knoa.frontend logger）+ 进程内 metrics 计数，方便 curl /api/metrics
一眼看到"前端错了多少"。

ponytail: 不引依赖、不落库、best-effort；公开写端点，学习项目够用
（生产应加限流/鉴权，面试可讲）。
"""
import json
import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Request

from app.core.metrics import record

logger = logging.getLogger("knoa.frontend")
router = APIRouter()

# 单条上报 payload 上限：事件只是极小的结构化 JSON，64KB 绰绰有余
MAX_EVENT_BYTES = 64 * 1024
# 日志单行化后单字段截断长度，防止异常超长内容刷屏
MAX_FIELD_LEN = 2000

# 轻量内存限流（best-effort，单进程够用；多副本应换 Redis）
_RATE_LIMIT = 200       # 每窗口允许的最大请求数
_RATE_WINDOW = 60.0     # 窗口秒数
_hits: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    window = _hits[ip]
    # 清掉窗口外的旧命中
    while window and now - window[0] > _RATE_WINDOW:
        window.pop(0)
    # 窗口已空：删除该 IP 的 key，避免 _hits dict 随不同访客无限增长（内存泄漏）
    if not window:
        _hits.pop(ip, None)
        return False
    if len(window) >= _RATE_LIMIT:
        return True
    window.append(now)
    return False


def _sanitize(value, limit: int = MAX_FIELD_LEN) -> str:
    """单行化 + 截断：去掉换行/回车（防日志注入伪造行），超长截断。"""
    if not isinstance(value, str):
        value = str(value)
    return " ".join(value.split())[:limit]


async def _read_capped(request: Request, limit: int) -> bytes:
    """带上限地读取请求体，防止超大 payload 撑爆内存。"""
    total = 0
    chunks = []
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise ValueError("payload too large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/events")
async def receive_event(request: Request):
    # 限流：保护这个公开写端点在被刷时拖垮日志/metrics
    if _rate_limited(_client_ip(request)):
        return {"ok": False, "error": "rate limited"}

    # body 体积上限：超大直接拒，避免无界读内存
    try:
        raw = await _read_capped(request, MAX_EVENT_BYTES)
    except ValueError:
        return {"ok": False, "error": "payload too large"}

    try:
        payload = json.loads(raw)
    except Exception:
        return {"ok": False}

    if not isinstance(payload, dict):
        return {"ok": False}

    etype = _sanitize(payload.get("type", "unknown"), 64)
    level = _sanitize(payload.get("level", "error"), 16)
    msg = _sanitize(payload.get("message", ""))
    src = _sanitize(payload.get("url", ""), 512)

    # 结构化日志：前端事件统一进 knoa.frontend logger（已单行化，防注入）
    if level == "error":
        logger.error("frontend %s: %s @ %s", etype, msg, src)
    elif level == "warn":
        logger.warning("frontend %s: %s @ %s", etype, msg, src)
    else:
        logger.info("frontend %s: %s @ %s", etype, msg, src)

    # 语义指标：与 HTTP 传输层(/api/events)分开计，方便单独看前端错误量
    record("frontend_event", 0.0, 200, level == "error")
    return {"ok": True}
