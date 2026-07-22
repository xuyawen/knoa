"""建表 + 写入 KB 元数据 + 种子 trending 数据。可执行: python -m app.data.seed"""
import asyncio
from datetime import date

from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.db import KnowledgeBase, Trending

KB_SEEDS = [
    {"id": "compliance", "name": "合规库", "icon": "compliance", "category": "合规"},
    {"id": "ads", "name": "广告投放", "icon": "ads", "category": "广告"},
    {"id": "logistics", "name": "物流仓储", "icon": "logistics", "category": "物流"},
    {"id": "selection", "name": "选品策略", "icon": "selection", "category": "选品"},
    {"id": "service", "name": "客服话术", "icon": "service", "category": "客服"},
]

TRENDING_SEEDS = [
    {"question": "FBA长期仓储费怎么算？", "count": 38},
    {"question": "新品冷启动广告预算怎么分配？", "count": 31},
    {"question": "类目审核需要哪些资质？", "count": 27},
    {"question": "退货率过高如何申诉？", "count": 19},
]


async def main():
    await init_db()

    async with AsyncSessionLocal() as db:
        # KB 元数据 (幂等: 已存在则跳过)
        for seed in KB_SEEDS:
            existing = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == seed["id"]))
            if not existing:
                db.add(KnowledgeBase(**seed))
            else:
                # 幂等回填 category（老库可能缺该字段值）
                existing.category = seed.get("category")
        await db.flush()

        # 种子 trending (写入今天)
        today = date.today()
        existing_trending = await db.scalar(
            select(Trending).where(Trending.date == today)
        )
        if not existing_trending:
            for t in TRENDING_SEEDS:
                db.add(Trending(question=t["question"], count=t["count"], date=today))

        await db.commit()

    print(f"Seed done: {len(KB_SEEDS)} KBs + {len(TRENDING_SEEDS)} trending items.")


if __name__ == "__main__":
    asyncio.run(main())
