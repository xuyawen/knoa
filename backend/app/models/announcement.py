"""系统公告 Pydantic 模型。"""
from app.models.knowledge import CamelModel


class AnnouncementOut(CamelModel):
    id: str
    title: str
    content: str
    level: str = "info"   # info | warn | critical
    pinned: bool = False
    createdAt: str

    @classmethod
    def from_orm(cls, a) -> "AnnouncementOut":
        return cls(
            id=str(a.id),
            title=a.title,
            content=a.content,
            level=a.level,
            pinned=bool(a.pinned),
            createdAt=a.created_at.isoformat() if a.created_at else "",
        )
