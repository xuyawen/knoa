"""迁移契约测试：Alembic upgrade head 必须建出全部 14 张业务表 + alembic_version。"""
import os

import asyncpg
import pytest


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
    # 14 张业务表 + alembic_version = 15
    assert n == 15, f"期望 15 张表（14 业务表 + alembic_version），实际 {n}"
