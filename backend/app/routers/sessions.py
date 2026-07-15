from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatMessage, ChatSession
from app.deps import get_db
from app.models.chat import (
    SessionCreateIn,
    SessionDetailOut,
    SessionMessageOut,
    SessionOut,
)

router = APIRouter()


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """会话列表：id / 标题（无标题回退首条用户消息）/ 更新时间 / 消息数。"""
    result = await db.execute(
        select(ChatSession).order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()

    out = []
    for s in sessions:
        msg_count = await db.scalar(
            select(func.count(ChatMessage.id)).where(ChatMessage.session_id == s.id)
        )
        title = s.title
        if not title:
            first_user = await db.scalar(
                select(ChatMessage.content)
                .where(ChatMessage.session_id == s.id, ChatMessage.role == "user")
                .order_by(ChatMessage.created_at)
                .limit(1)
            )
            title = (first_user[:24] + "…") if first_user else "新对话"
            out.append(
                SessionOut(
                    id=str(s.id),
                    title=title,
                    updated_at=s.updated_at.isoformat() if s.updated_at else "",
                    msg_count=msg_count or 0,
                    summary=s.summary,
                )
            )
    return out


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    payload: SessionCreateIn,
    db: AsyncSession = Depends(get_db),
):
    """新建空会话（前端「新建对话」调用），返回 id。"""
    session = ChatSession(title=payload.title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionOut(
        id=str(session.id),
        title=session.title or "新对话",
        updated_at=session.updated_at.isoformat() if session.updated_at else "",
        msg_count=0,
        summary=session.summary,
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """拉取某会话的全部消息（按时间正序）。"""
    session = await db.scalar(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    msgs = result.scalars().all()

    return SessionDetailOut(
        id=str(session.id),
        title=session.title or "新对话",
        summary=session.summary,
        messages=[
            SessionMessageOut(
                role=m.role,
                content=m.content,
                citations=m.citations,
                sources=m.sources,
                attachments=m.attachments,
            )
            for m in msgs
        ],
    )
