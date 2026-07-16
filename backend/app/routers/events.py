"""前端可观测上报端点（零依赖）。

前端 monitor.ts 通过 sendBeacon/fetch 把浏览器内的错误、未捕获 Promise
拒绝、首屏性能埋点发到这里。后端只做两件事：结构化日志（进独立的
knoa.frontend logger）+ 进程内 metrics 计数，方便 curl /api/metrics
一眼看到"前端错了多少"。

ponytail: 不引依赖、不落库、best-effort；公开写端点，学习项目够用
（生产应加限流/鉴权，面试可讲）。
"""
import logging

from fastapi import APIRouter, Request

from app.core.metrics import record

logger = logging.getLogger("knoa.frontend")
router = APIRouter()


@router.post("/events")
async def receive_event(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return {"ok": False}

    if not isinstance(payload, dict):
        return {"ok": False}

    etype = payload.get("type", "unknown")
    level = payload.get("level", "error")
    msg = payload.get("message", "")
    src = payload.get("url", "")

    # 结构化日志：前端事件统一进 knoa.frontend logger
    if level == "error":
        logger.error("frontend %s: %s @ %s", etype, msg, src)
    elif level == "warn":
        logger.warning("frontend %s: %s @ %s", etype, msg, src)
    else:
        logger.info("frontend %s: %s @ %s", etype, msg, src)

    # 语义指标：与 HTTP 传输层(/api/events)分开计，方便单独看前端错误量
    record("frontend_event", 0.0, 200, level == "error")
    return {"ok": True}
