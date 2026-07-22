"""操作日志 Pydantic 模型 + best-effort 写入 helper。"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import OperationLog
from app.models.knowledge import CamelModel

logger = logging.getLogger("knoa.ops")

# action -> 中文标签（前端操作记录表「操作类型」列直接复用）
ACTION_LABELS = {
    "login": "登录",
    "upload": "上传文档",
    "approve": "审核通过",
    "reject": "审核驳回",
    "delete": "删除文档",
    "ask": "AI 问答",
    "download": "下载",
}


class OperationLogOut(CamelModel):
    id: str
    userId: str | None = None
    displayName: str | None = None
    action: str
    actionLabel: str = ""
    relatedDocId: str | None = None
    detail: str | None = None
    createdAt: str

    @classmethod
    def from_orm(cls, log: "OperationLog") -> "OperationLogOut":
        return cls(
            id=str(log.id),
            userId=str(log.user_id) if log.user_id else None,
            displayName=log.display_name,
            action=log.action,
            actionLabel=ACTION_LABELS.get(log.action, log.action),
            relatedDocId=str(log.related_doc_id) if log.related_doc_id else None,
            detail=log.detail,
            createdAt=log.created_at.isoformat() if log.created_at else "",
        )


async def record_operation(
    db: AsyncSession,
    user,
    action: str,
    related_doc_id: str | None = None,
    detail: str | None = None,
) -> None:
    """best-effort 写一条操作日志；失败仅告警不抛，绝不阻塞主流程。

    内部自行 commit，因此即使调用方（如登录）本身不 commit 也能持久化；
    若调用方随后还会 commit，多次 commit 无害。
    """
    try:
        log = OperationLog(
            user_id=str(user.id) if user and getattr(user, "id", None) else None,
            display_name=user.display_name if user and getattr(user, "display_name", None) else None,
            action=action,
            related_doc_id=str(related_doc_id) if related_doc_id else None,
            detail=(detail or "")[:500] if detail else None,
        )
        db.add(log)
        await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("record_operation(%s) failed: %s", action, e)
