"""回填文档的 department_id 与 tags（P5 部门树 / 标签筛选需要真实数据）。

当前种子文档这两个字段均为空，导致部门树、标签筛选无内容可演示。
本脚本幂等：仅对 department_id 为 NULL 且 tags 为空的文档赋值，已填过的不动。
可执行: python -m app.data.seed_doc_meta
"""
import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.db import Department, Document, KnowledgeBase

# 标签池：按文档序号轮询分配 1~2 个，模拟真实分类
TAG_POOL = ["政策解读", "操作指引", "风险预警", "FAQ", "内部培训", "案例", "模板"]


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
                changed = False
                if d.department_id is None:
                    d.department_id = depts[i % len(depts)].id
                    changed = True
                if not d.tags:
                    tags = [TAG_POOL[i % len(TAG_POOL)]]
                    if i % 3 == 0:
                        tags.append(TAG_POOL[(i + 1) % len(TAG_POOL)])
                    d.tags = tags
                    changed = True
                if changed:
                    updated += 1
        await db.commit()
        print(f"doc meta backfilled: {updated} docs across {len(kbs)} KBs.")


if __name__ == "__main__":
    asyncio.run(main())
