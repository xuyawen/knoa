from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import paginate
from app.core.security import get_current_user
from app.db import ChatMessage, ChatSession, User
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
    按会话更新时间倒序，支持按来源类型过滤（kb/web/graph）。

    核心查询用 PostgreSQL DISTINCT ON 把每条 user 消息与它之后最近的 assistant
    消息配对；来源过滤在 Python 侧对 JSONB sources 做计数（避免 SQL 层解 JSON）。
    """
    user_id = str(user.id)

    # 用原生 SQL 做「user→紧邻 assistant」配对。
    # PostgreSQL DISTINCT ON (u.id) 保证每条 user 消息只取 created_at 最小的那条 assistant 回答，
    # 即用户提问后「紧跟」的第一条回答。外层再按会话时间倒序做全局排序。
    sql = text("""
        SELECT * FROM (
            SELECT DISTINCT ON (u.id)
                s.id           AS session_id,
                s.title        AS session_title,
                s.updated_at   AS session_updated,
                u.id           AS user_msg_id,
                u.content      AS question,
                a.content      AS answer,
                a.sources      AS sources,
                u.created_at   AS q_created
            FROM chat_message u
            JOIN chat_session s ON s.id = u.session_id
            JOIN chat_message a ON a.session_id = u.session_id
                AND a.role = 'assistant'
                AND a.created_at > u.created_at
            WHERE s.user_id = :user_id
              AND u.role = 'user'
            ORDER BY u.id, a.created_at ASC
        ) paired
        ORDER BY paired.session_updated DESC, paired.q_created ASC
    """)

    result = await db.execute(sql, {"user_id": user_id})
    rows = result.mappings().all()

    # 来源过滤 + 字段映射
    filtered = []
    for r in rows:
        sources = r["sources"] or []
        kb_c = sum(1 for s in sources if s.get("sourceType") == "kb")
        web_c = sum(1 for s in sources if s.get("sourceType") == "web")
        graph_c = sum(1 for s in sources if s.get("sourceType") == "graph")

        if f == "kb" and kb_c == 0:
            continue
        if f == "web" and web_c == 0:
            continue
        if f == "graph" and graph_c == 0:
            continue

        updated = r["session_updated"]
        filtered.append(
            {
                "session_id": str(r["session_id"]),
                "session_title": r["session_title"] or "（新会话）",
                "question": r["question"],
                "answer": r["answer"],
                "sources": sources,
                "source_count": len(sources),
                "kb_count": kb_c,
                "web_count": web_c,
                "graph_count": graph_c,
                "created_at": updated.isoformat() if updated else "",
                "_sort_key": (updated, r["q_created"]),
            }
        )

    total = len(filtered)
    # 手动分页（已在内存中完成过滤）
    start = (page - 1) * size
    page_items = filtered[start : start + size]
    pages = max(1, (total + size - 1) // size) if total else 1

    out = [
        RecordOut(
            id=f'{item["session_id"]}-{idx}',
            session_id=item["session_id"],
            session_title=item["session_title"],
            question=item["question"],
            answer=item["answer"],
            sources=item["sources"],
            source_count=item["source_count"],
            kb_count=item["kb_count"],
            web_count=item["web_count"],
            graph_count=item["graph_count"],
            created_at=item["created_at"],
        )
        for idx, item in enumerate(page_items)
    ]
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
