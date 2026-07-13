"""长期记忆接口（Phase 2 T4 Mem0 轻量自研版）。

仅暴露给当前登录用户自身：
- GET  /api/memories       列出该用户全部长期记忆（按时间倒序）
- DELETE /api/memories/{id}  删除某一条
- DELETE /api/memories      清空该用户全部记忆

写记忆发生在每次问答的后台任务里（见 agent.py），这里只做「可读 / 可忘」。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Memory, User
from app.deps import get_db
from app.core.security import get_current_user
from app.models.knowledge import CamelModel

router = APIRouter()


class MemoryOut(CamelModel):
    id: str
    content: str
    type: str | None = None
    createdAt: str | None = None


class DeleteResult(CamelModel):
    ok: bool
    deleted: int | None = None


@router.get("/memories")
async def list_memories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(Memory)
        .where(Memory.user_id == user.id)
        .order_by(Memory.created_at.desc())
    )
    rows = result.scalars().all()
    return {
        "memories": [
            MemoryOut(
                id=str(m.id),
                content=m.content,
                type=m.meta_type,
                createdAt=m.created_at.isoformat() if m.created_at else None,
            ).model_dump(by_alias=True)
            for m in rows
        ]
    }


@router.delete("/memories/{memory_id}", response_model=DeleteResult)
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeleteResult:
    try:
        mid = uuid.UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="非法的记忆 ID")
    row = (
        await db.execute(select(Memory).where(Memory.id == mid))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="记忆不存在")
    if str(row.user_id) != str(user.id):
        raise HTTPException(status_code=403, detail="无权删除他人记忆")
    await db.delete(row)
    await db.commit()
    return DeleteResult(ok=True)


@router.delete("/memories", response_model=DeleteResult)
async def clear_memories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeleteResult:
    rows = (
        await db.execute(select(Memory).where(Memory.user_id == user.id))
    ).scalars().all()
    for r in rows:
        await db.delete(r)
    await db.commit()
    return DeleteResult(ok=True, deleted=len(rows))
