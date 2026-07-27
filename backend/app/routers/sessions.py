from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import paginate
from app.core.security import get_current_user
from app.db import ChatMessage, ChatSession, MessageFeedback, User
from app.deps import get_db
from app.models.chat import (
    RecordOut,
    SessionCreateIn,
    SessionDetailOut,
    SessionMessageOut,
    SessionOut,
)
from app.models.common import PaginatedOut

router = APIRouter()


@router.get("/records", response_model=PaginatedOut[RecordOut])
async def list_records(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    f: str = Query("all", pattern="^(all|kb|web|graph)$"),  # noqa: E741
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """检索记录分页：返回当前用户的问答对（user 提问 + 紧跟的 assistant 回答），
    按提问时间倒序，支持按来源类型过滤（kb/web/graph）。

    每条 user 消息用 LATERAL 子查询配对其后最早的 assistant 回答——
    旧实现的 `a.created_at > u.created_at` range join 会在单会话内产生
    二次方笛卡尔积再由 DISTINCT ON 去重，消息一多就慢；来源过滤用
    JSONB 包含运算符在 SQL 侧完成，分页与计数不再把全量拉进内存。
    """
    user_id = str(user.id)

    # 来源类型过滤：sources 是 JSONB 数组，@> '[{...}]' 表示「数组中任一
    # 元素包含该键值」。graph 额外兼容 graph-multihop（多跳推理来源）。
    # 取自固定字典（非用户输入），拼接安全。
    source_filter = {
        "kb": 'AND a.sources @> \'[{"sourceType": "kb"}]\'::jsonb',
        "web": 'AND a.sources @> \'[{"sourceType": "web"}]\'::jsonb',
        "graph": (
            'AND (a.sources @> \'[{"sourceType": "graph"}]\'::jsonb'
            ' OR a.sources @> \'[{"sourceType": "graph-multihop"}]\'::jsonb)'
        ),
    }.get(f, "")

    sql = text(f"""
        SELECT *, COUNT(*) OVER() AS total_count FROM (
            SELECT
                s.id           AS session_id,
                s.title        AS session_title,
                u.id           AS user_msg_id,
                u.content      AS question,
                a.content      AS answer,
                a.sources      AS sources,
                u.created_at   AS q_created
            FROM chat_message u
            JOIN chat_session s ON s.id = u.session_id
            JOIN LATERAL (
                SELECT m.content, m.sources
                FROM chat_message m
                WHERE m.session_id = u.session_id
                  AND m.role = 'assistant'
                  AND m.created_at > u.created_at
                ORDER BY m.created_at ASC
                LIMIT 1
            ) a ON true
            WHERE s.user_id = :user_id
              AND u.role = 'user'
              {source_filter}
        ) paired
        ORDER BY paired.q_created DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(
        sql, {"user_id": user_id, "limit": size, "offset": (page - 1) * size}
    )
    rows = result.mappings().all()
    # 窗口 COUNT 在 LIMIT 之前计算，任一行都携带全量 total
    total = int(rows[0]["total_count"]) if rows else 0

    out = []
    for r in rows:
        sources = r["sources"] or []
        q_created = r["q_created"]
        out.append(
            RecordOut(
                id=str(r["user_msg_id"]),
                session_id=str(r["session_id"]),
                session_title=r["session_title"] or "（新会话）",
                question=r["question"],
                answer=r["answer"],
                sources=sources,
                source_count=len(sources),
                kb_count=sum(1 for s in sources if s.get("sourceType") == "kb"),
                web_count=sum(1 for s in sources if s.get("sourceType") == "web"),
                graph_count=sum(
                    1 for s in sources if s.get("sourceType") in ("graph", "graph-multihop")
                ),
                # 记录时间 = 提问时间（旧实现误用会话 updated_at，导致
                # 「修改过标题/后续又聊过的会话」里所有记录都显示最后活跃日）
                created_at=q_created.isoformat() if q_created else "",
            )
        )
    pages = max(1, (total + size - 1) // size) if total else 1
    return {
        "items": out,
        "total": total,
        "page": page,
        "page_size": size,
        "pages": pages,
    }


# ── 会话 CRUD ──────────────────────────────────────────────


@router.get("/sessions", response_model=PaginatedOut[SessionOut])
async def list_sessions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """会话列表分页：仅返回当前登录用户自己的会话。"""
    user_id = str(user.id)
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
    )
    rows, total = await paginate(db, stmt, page=page, page_size=size)
    sessions = [r[0] for r in rows]

    # 聚合查询消除 N+1：一次性取当前页会话的消息数与首条用户消息
    ids = [s.id for s in sessions]
    count_by_id: dict = {}
    first_by_id: dict = {}
    if ids:
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
            title = (first_user[:24] + "\u2026") if first_user else "新对话"
        out.append(
            SessionOut(
                id=str(s.id),
                title=title,
                updated_at=s.updated_at.isoformat() if s.updated_at else "",
                msg_count=count_by_id.get(s.id, 0),
                summary=s.summary,
            )
        )
    pages = max(1, (total + size - 1) // size) if total else 1
    return {
        "items": out,
        "total": total,
        "page": page,
        "page_size": size,
        "pages": pages,
    }


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
                id=str(m.id),
                role=m.role,
                content=m.content,
                citations=m.citations,
                sources=m.sources,
                attachments=m.attachments,
                thinking_steps=m.thinking_steps,
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
    # message_feedback.message_id 外键无 ON DELETE CASCADE，
    # 必须先清反馈行，否则删消息会触发 FK 违约 500
    msg_ids = (
        await db.execute(
            select(ChatMessage.id).where(ChatMessage.session_id == session_id)
        )
    ).scalars().all()
    if msg_ids:
        await db.execute(delete(MessageFeedback).where(MessageFeedback.message_id.in_(msg_ids)))
    # 先删消息，再删会话
    await db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    await db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    await db.commit()
    return {"ok": True}


@router.delete("/sessions/{session_id}/messages")
async def clear_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """清空会话全部消息（前端「清空对话」按钮）：保留会话壳，删除所有消息。

    同时重置滚动摘要边界（summary / summarized_count）——否则旧摘要会继续
    注入后续提问的上下文，出现「界面清空了、模型还记得旧内容」的割裂。
    """
    session = await db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == str(user.id),
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    msg_ids = (
        await db.execute(
            select(ChatMessage.id).where(ChatMessage.session_id == session_id)
        )
    ).scalars().all()
    if msg_ids:
        await db.execute(delete(MessageFeedback).where(MessageFeedback.message_id.in_(msg_ids)))
        await db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    session.summary = None
    session.summarized_count = 0
    await db.commit()
    return {"ok": True}


@router.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """重命名会话（侧边栏铅笔按钮）；仅限自己的会话。"""
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    session = await db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == str(user.id),
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    session.title = title[:60]
    await db.commit()
    return {"ok": True, "title": session.title}


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除单条消息（前端「重新生成」先移除旧回答再重问）。

    仅能删除自己会话里的消息（join 会话归属校验）。
    """
    msg = await db.scalar(
        select(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(ChatMessage.id == message_id, ChatSession.user_id == str(user.id))
    )
    if msg is None:
        raise HTTPException(status_code=404, detail="消息不存在")
    # 同会话删除：message_feedback 外键无级联，必须先清反馈行
    await db.execute(delete(MessageFeedback).where(MessageFeedback.message_id == msg.id))
    await db.execute(delete(ChatMessage).where(ChatMessage.id == msg.id))
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
    # 同 delete_session：先清反馈行（外键无级联），再级联删除消息
    msg_ids = (
        await db.execute(
            select(ChatMessage.id).where(ChatMessage.session_id.in_(owned_ids))
        )
    ).scalars().all()
    if msg_ids:
        await db.execute(delete(MessageFeedback).where(MessageFeedback.message_id.in_(msg_ids)))
    # 级联删除消息
    await db.execute(
        delete(ChatMessage).where(ChatMessage.session_id.in_(owned_ids))
    )
    result = await db.execute(
        delete(ChatSession).where(ChatSession.id.in_(owned_ids))
    )
    await db.commit()
    return {"ok": True, "deleted": result.rowcount}
