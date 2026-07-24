from fastapi import APIRouter, Depends

from app.core.metrics import snapshot
from app.core.security import get_current_user

router = APIRouter()


@router.get("/metrics", dependencies=[Depends(get_current_user)])
async def metrics():
    """运行指标快照（聚合数据，无 PII）。需登录可见，避免向匿名暴露运行态势。"""
    return snapshot()
