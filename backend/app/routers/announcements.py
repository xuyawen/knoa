"""Phase 1 业务统计：系统公告（通知中心 / 系统设置管理）。"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Announcement, User, UserAnnouncementRead
from app.deps import get_db
from app.models.announcement import AnnouncementOut
from app.core.security import get_current_user, require_roles

router = APIRouter()


class AnnouncementCreate(BaseModel):
    title: str = Field(..., max_length=200)
    content: str
    level: str = "info"  # info | warning | success | error
    pinned: bool = False


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    content: str | None = None
    level: str | None = None
    pinned: bool | None = None


@router.get("/announcements")
async def list_announcements(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """公告列表：pinned 置顶优先，再按时间倒序。所有登录用户可见。

    按当前用户标注 read 字段：查该用户已读的公告 id 集合，列表里命中即 read=True。
    """
    rows = (
        await db.execute(
            select(Announcement)
            .order_by(Announcement.pinned.desc(), Announcement.created_at.desc())
        )
    ).scalars().all()
    read_ids = set(
        (await db.scalars(
            select(UserAnnouncementRead.announcement_id).where(
                UserAnnouncementRead.user_id == user.id
            )
        )).all()
    )
    return [AnnouncementOut.from_orm(r, read=(r.id in read_ids)) for r in rows]


@router.post("/announcements/{ann_id}/read", status_code=200)
async def mark_announcement_read(
    ann_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """标记某公告为已读（幂等 upsert，重复标记不报错）。"""
    try:
        ann_uuid = uuid.UUID(ann_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="公告 ID 格式错误")
    exists = await db.scalar(
        select(Announcement).where(Announcement.id == ann_uuid)
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="公告不存在")
    # 已读记录：复合主键 (user_id, announcement_id)，冲突即跳过
    await db.execute(
        text(
            "INSERT INTO user_announcement_read (user_id, announcement_id, read_at) "
            "VALUES (:uid, :aid, now()) "
            "ON CONFLICT (user_id, announcement_id) DO NOTHING"
        ),
        {"uid": user.id, "aid": ann_uuid},
    )
    await db.commit()
    return {"ok": True}


@router.post("/announcements", response_model=AnnouncementOut, status_code=201)
async def create_announcement(
    payload: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_roles("admin")),
):
    a = Announcement(
        id=uuid.uuid4(),
        title=payload.title,
        content=payload.content,
        level=payload.level,
        pinned=payload.pinned,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return AnnouncementOut.from_orm(a)


@router.put("/announcements/{ann_id}", response_model=AnnouncementOut)
async def update_announcement(
    ann_id: str,
    payload: AnnouncementUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_roles("admin")),
):
    a = await db.scalar(select(Announcement).where(Announcement.id == ann_id))
    if a is None:
        raise HTTPException(status_code=404, detail="公告不存在")
    if payload.title is not None:
        a.title = payload.title
    if payload.content is not None:
        a.content = payload.content
    if payload.level is not None:
        a.level = payload.level
    if payload.pinned is not None:
        a.pinned = payload.pinned
    await db.commit()
    await db.refresh(a)
    return AnnouncementOut.from_orm(a)


@router.delete("/announcements/{ann_id}", status_code=204)
async def delete_announcement(
    ann_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_roles("admin")),
):
    a = await db.scalar(select(Announcement).where(Announcement.id == ann_id))
    if a is None:
        raise HTTPException(status_code=404, detail="公告不存在")
    await db.delete(a)
    await db.commit()
