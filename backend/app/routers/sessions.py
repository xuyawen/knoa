from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db import ChatMessage, ChatSession, User
from app.deps import get_db
from app.models.chat import (
    SessionCreateIn,
    SessionDetailOut,
    SessionMessageOut,
    SessionOut,
)

router = APIRouter()


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """会话列表：仅返回当前登录用户自己的会话。"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == str(user.id))
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    if not sessions:
        return []

    # 聚合查询消除 N+1：一次性取全部会话的消息数与首条用户消息，而非逐条查
    ids = [s.id for s in sessions]
    counts = (
        await db.execute(
            select(ChatMessage.session_id, func.count(ChatMessage.id))
            .where(ChatMessage.session_id.in_(ids))
            .group_by(ChatMessage.session_id)
        )
    ).all()
    count_by_id = {sid: c for sid, c in counts}

    first_msgs = (
        await db.execute(
            select(ChatMessage.session_id, ChatMessage.content)
            .where(ChatMessage.session_id.in_(ids), ChatMessage.role == "user")
            .order_by(ChatMessage.session_id, ChatMessage.created_at)
            .distinct(ChatMessage.session_id)
        )
    ).all()
    first_by_id = {sid: content for sid, content in first_msgs}

    out = []
    for s in sessions:
        title = s.title
        if not title:
            first_user = first_by_id.get(s.id)
            title = (first_user[:24] + "…") if first_user else "新对话"
        out.append(
            SessionOut(
                id=str(s.id),
                title=title,
                updated_at=s.updated_at.isoformat() if s.updated_at else "",
                msg_count=count_by_id.get(s.id, 0),
                summary=s.summary,
            )
        )
    return out


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    payload: SessionCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """新建空会话（前端「新建对话」调用），返回 id；绑定到当前用户。"""
    session = ChatSession(title=payload.title, user_id=str(user.id))
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
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """拉取某会话的全部消息（按时间正序）；仅限当前用户自己的会话。"""
    session = await db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == str(user.id),
        )
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


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除单个会话（级联删除其消息）；仅限当前用户自己的会话。"""
    session = await db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == str(user.id),
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    # 先删消息，再删会话
    await db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    await db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    await db.commit()
    return {"ok": True}


@router.post("/sessions/batch-delete")
async def batch_delete_sessions(
    payload: dict[str, list[str]],  # {"ids": [...]}
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """批量删除会话；仅删除属于自己的会话，避免越权删除他人会话。"""
    ids = payload.get("ids", [])
    if not ids:
        return {"ok": True, "deleted": 0}
    owned = (
        await db.execute(
            select(ChatSession.id).where(
                ChatSession.id.in_(ids),
                ChatSession.user_id == str(user.id),
            )
        )
    ).scalars().all()
    owned_ids = [str(x) for x in owned]
    if not owned_ids:
        return {"ok": True, "deleted": 0}
    # 级联删除消息
    await db.execute(
        delete(ChatMessage).where(ChatMessage.session_id.in_(owned_ids))
    )
    result = await db.execute(
        delete(ChatSession).where(ChatSession.id.in_(owned_ids))
    )
    await db.commit()
    return {"ok": True, "deleted": result.rowcount}
