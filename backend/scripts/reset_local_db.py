"""本地开发库复位：DROP 并重建 knoa 库（postgres :5433）。

仅用于本地环境清洗重建，不可用于生产。
跑法（必须在 backend/ 目录下，以读到 .env）：
    cd X:/workspace/knoa/backend
    .venv/Scripts/python.exe scripts/reset_local_db.py
"""
import asyncio
import sys

import asyncpg

sys.path.insert(0, r"X:\workspace\knoa\backend")

DB_USER = "knoa"
DB_PASS = "knoa"
DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "knoa"
ADMIN_DB = "postgres"


async def main() -> None:
    # 连 postgres 库（不是目标库），才能 DROP 目标库
    conn = await asyncpg.connect(
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT,
        database=ADMIN_DB,
    )
    # 终止目标库上的活跃连接，否则 DROP 会被占用
    await conn.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1",
        DB_NAME,
    )
    await conn.execute(f'DROP DATABASE IF EXISTS "{DB_NAME}"')
    await conn.execute(f'CREATE DATABASE "{DB_NAME}" WITH ENCODING = \'UTF8\'')
    await conn.close()
    print(f"[reset] dropped & recreated database '{DB_NAME}'")


if __name__ == "__main__":
    asyncio.run(main())
