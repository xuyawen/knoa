from fastapi import APIRouter

from app.core.metrics import snapshot

router = APIRouter()


@router.get("/metrics")
async def metrics():
    """进程内运行指标快照（聚合数据，无 PII）。供监控/压测观察使用。"""
    return snapshot()
