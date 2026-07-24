import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db import ChatMessage, ChatSession, MessageFeedback, User
from app.deps import get_db
from app.models.knowledge import CamelModel

router = APIRouter()


class FeedbackIn(CamelModel):
    message_id: str = Field(..., description="服务端返回的回答消息 id")
    rating: str = Field(..., pattern="^(up|down)$", description="'up' 或 'down'")


@router.post("/feedback")
async def create_feedback(
    payload: FeedbackIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """对一条回答提交/更新反馈（upsert）；需登录。"""
    try:
        msg_id = uuid.UUID(payload.message_id)
    except ValueError:
        raise HTTPException(400, "invalid message_id") from None

    msg = (
        await db.execute(select(ChatMessage).where(ChatMessage.id == msg_id))
    ).scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "message not found")

    existing = (
        await db.execute(
            select(MessageFeedback).where(MessageFeedback.message_id == msg_id)
        )
    ).scalar_one_or_none()

    if existing:
        existing.rating = payload.rating
    else:
        db.add(MessageFeedback(message_id=msg_id, rating=payload.rating))

    await db.commit()
    return {"ok": True, "rating": payload.rating}


@router.delete("/feedback/{message_id}")
async def delete_feedback(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """取消对某条回答的反馈；需登录且只能取消自己的反馈。"""
    try:
        msg_id = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(400, "invalid message_id") from None

    # 归属校验：feedback → chat_message → chat_session.user_id，防越权删他人反馈
    row = (
        await db.execute(
            select(MessageFeedback, ChatSession.user_id)
            .join(ChatMessage, ChatMessage.id == MessageFeedback.message_id)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(MessageFeedback.message_id == msg_id)
        )
    ).first()
    if row is None:
        return {"ok": True}  # 幂等：原本就没有该反馈
    fb, session_user_id = row
    if str(user.id) != session_user_id and user.role != "admin":
        raise HTTPException(status_code=403, detail="无权删除他人的反馈")

    await db.execute(delete(MessageFeedback).where(MessageFeedback.message_id == msg_id))
    await db.commit()
    return {"ok": True}
