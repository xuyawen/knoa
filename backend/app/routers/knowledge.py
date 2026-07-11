from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, KnowledgeBase
from app.deps import get_db
from app.models.knowledge import (
    HealthItemOut,
    KnowledgeBaseOut,
    KnowledgeBasesResponse,
)

router = APIRouter()

# ponytail: Phase 1 覆盖率用固定映射, 真实系统按检索命中/文档时效计算
COVERAGE_MAP = {
    "compliance": 0.82,
    "ads": 0.76,
    "logistics": 0.69,
    "selection": 0.61,
    "service": 0.55,
}


@router.get("/knowledge-bases", response_model=KnowledgeBasesResponse)
async def get_knowledge_bases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at))
    kbs = result.scalars().all()

    kb_list = []
    health_list = []
    for kb in kbs:
        doc_count = await db.scalar(
            select(func.count(Document.id)).where(Document.kb_id == kb.id)
        )
        latest = await db.scalar(
            select(func.max(Document.updated_at)).where(Document.kb_id == kb.id)
        )

        badge = None
        badge_type = None
        if kb.pending_count > 0:
            badge = f"{kb.pending_count} 份待复核"
            badge_type = "danger"

        kb_list.append(
            KnowledgeBaseOut(
                id=kb.id, name=kb.name, icon=kb.icon,
                badge=badge, badge_type=badge_type,
            )
        )
        health_list.append(
            HealthItemOut(
                kb=kb.name,
                doc_count=doc_count or 0,
                updated_at=latest.isoformat() if latest else "",
                coverage=COVERAGE_MAP.get(kb.id, 0.5),
            )
        )

    return KnowledgeBasesResponse(knowledge_bases=kb_list, health=health_list)
