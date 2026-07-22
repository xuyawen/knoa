"""迁移契约测试：Alembic upgrade head 必须建出 metadata 定义的全部表 + alembic_version。"""
import os

import asyncpg
import pytest

from app.db import Base


@pytest.mark.asyncio
async def test_alembic_creates_all_tables():
    # 与 DATABASE_URL 同源（去掉 +asyncpg 驱动前缀给 asyncpg 用）
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn=url)
    try:
        n = await conn.fetchval(
            "select count(*) from information_schema.tables where table_schema='public'"
        )
    finally:
        await conn.close()
    # 全部业务表（来自 ORM metadata）+ alembic_version
    expected = len(Base.metadata.tables) + 1
    assert n == expected, f"期望 {expected} 张表（{len(Base.metadata.tables)} 业务表 + alembic_version），实际 {n}"
