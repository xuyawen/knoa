"""系统公告 Pydantic 模型。"""
from app.models.knowledge import CamelModel


class AnnouncementOut(CamelModel):
    id: str
    title: str
    content: str
    level: str = "info"   # info | warn | critical
    pinned: bool = False
    createdAt: str
    read: bool = False    # 当前用户是否已读（列表接口按当前用户标注）

    @classmethod
    def from_orm(cls, a, read: bool = False) -> "AnnouncementOut":
        return cls(
            id=str(a.id),
            title=a.title,
            content=a.content,
            level=a.level,
            pinned=bool(a.pinned),
            createdAt=a.created_at.isoformat() if a.created_at else "",
            read=read,
        )
