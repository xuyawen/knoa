"""回填文档的 department_id（P5 部门树需要真实数据）。

当前种子文档该字段为空，导致部门树无内容可演示。
本脚本幂等：仅对 department_id 为 NULL 的文档赋值，已填过的不动。
可执行: python -m app.data.seed_doc_meta
"""
import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.db import Department, Document, KnowledgeBase


async def main():
    await init_db()
    async with AsyncSessionLocal() as db:
        depts = (await db.execute(select(Department).order_by(Department.sort_order))).scalars().all()
        if not depts:
            print("no departments seeded, skip.")
            return
        kbs = (await db.execute(select(KnowledgeBase))).scalars().all()
        updated = 0
        for kb in kbs:
            docs = (await db.execute(select(Document).where(Document.kb_id == kb.id))).scalars().all()
            for i, d in enumerate(docs):
                if d.department_id is None:
                    d.department_id = depts[i % len(depts)].id
                    updated += 1
        await db.commit()
        print(f"doc meta backfilled: {updated} docs across {len(kbs)} KBs.")


if __name__ == "__main__":
    asyncio.run(main())
