import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatMessage, MessageFeedback
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
):
    """对一条回答提交/更新反馈（upsert）。"""
    try:
        msg_id = uuid.UUID(payload.message_id)
    except ValueError:
        raise HTTPException(400, "invalid message_id")

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
):
    """取消对某条回答的反馈。"""
    try:
        msg_id = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(400, "invalid message_id")

    await db.execute(
        delete(MessageFeedback).where(MessageFeedback.message_id == msg_id)
    )
    await db.commit()
    return {"ok": True}
