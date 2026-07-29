"""验证本地重建结果：部门/用户/KB/授权/文档/向量化/密码。

跑法（backend/ 目录）：
    cd X:/workspace/knoa/backend
    .venv/Scripts/python.exe scripts/verify_rebuild.py
"""
import asyncio
import sys

sys.path.insert(0, r"X:\workspace\knoa\backend")

from sqlalchemy import func, select, text

from app.config import settings
from app.database import AsyncSessionLocal
from app.db import (
    Department,
    DocChunk,
    Document,
    KBDeptGrant,
    KnowledgeBase,
    User,
)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        n_dept = await db.scalar(select(func.count()).select_from(Department))
        n_user = await db.scalar(select(func.count()).select_from(User))
        n_kb = await db.scalar(select(func.count()).select_from(KnowledgeBase))
        n_grant = await db.scalar(select(func.count()).select_from(KBDeptGrant))
        n_doc = await db.scalar(select(func.count()).select_from(Document))
        n_doc_appr = await db.scalar(
            select(func.count()).select_from(Document).where(Document.status == "已审核")
        )
        n_chunk = await db.scalar(select(func.count()).select_from(DocChunk))
        n_chunk_emb = await db.scalar(
            select(func.count()).select_from(DocChunk).where(DocChunk.embedding.is_not(None))
        )

        res = await db.execute(
            text(
                "SELECT d.name, COUNT(u.id) FROM department d "
                "LEFT JOIN app_user u ON u.department_id=d.id "
                "GROUP BY d.name ORDER BY d.name"
            )
        )
        per_dept = res.all()

        admin = await db.scalar(select(User).where(User.username == settings.ADMIN_USERNAME))
        ops01 = await db.scalar(select(User).where(User.username == "ops01"))
        ops02 = await db.scalar(select(User).where(User.username == "ops02"))
        pw_editor = ops01.verify_password("q123321.") if ops01 else False
        pw_viewer = ops02.verify_password("q123321.") if ops02 else False

        res = await db.execute(
            text(
                "SELECT kb_id, d.name, g.level FROM kb_dept_grant g "
                "JOIN department d ON d.id=g.dept_id ORDER BY d.name"
            )
        )
        grants = res.all()

        res = await db.execute(
            text("SELECT kb_id, COUNT(*) FROM document GROUP BY kb_id ORDER BY kb_id")
        )
        per_kb = res.all()

    print("=== 计数 ===")
    print(f"  department       : {n_dept}")
    print(f"  user (含 admin) : {n_user}")
    print(f"  knowledge_base  : {n_kb}")
    print(f"  kb_dept_grant   : {n_grant}")
    print(f"  document        : {n_doc} (已审核 {n_doc_appr})")
    print(f"  doc_chunk      : {n_chunk} (含 embedding {n_chunk_emb})")
    print("\n=== 每部门员工数 (应均=10) ===")
    for name, c in per_dept:
        print(f"  {name}: {c}  {'OK' if c == 10 else '!!'}")
    print("\n=== admin ===")
    print(f"  username: {admin.username if admin else None}  exists={admin is not None}")
    print("\n=== 员工密码 q123321. (应 True) ===")
    print(f"  ops01(editor): {pw_editor}")
    print(f"  ops02(viewer): {pw_viewer}")
    print("\n=== 部门 KB 授权 (应 8 行, level=edit) ===")
    for kb_id, name, lvl in grants:
        print(f"  {name} -> {kb_id} [{lvl}]")
    print("\n=== 每 KB 文档数 (应均=2) ===")
    for kb_id, c in per_kb:
        print(f"  {kb_id}: {c}  {'OK' if c == 2 else '!!'}")


if __name__ == "__main__":
    asyncio.run(main())
