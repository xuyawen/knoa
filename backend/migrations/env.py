"""Alembic 环境（异步 Postgres / asyncpg）。

关键点：
- 数据库是异步的（postgresql+asyncpg），所以 env.py 用 create_async_engine
  + run_sync 把迁移派发到异步连接上（Alembic 官方推荐的 async 写法）。
- 连接串复用 app.config.settings.DATABASE_URL（来自 .env，绝不写死在 ini 里），
  这样 Alembic / init_db() 与运行时用的是同一套凭证。
- 测试时可设环境变量 ALEMBIC_TEST_DB=<dbname>，让 Alembic 临时连到
  另一个空库（不碰真实业务库），用于本地验证初始迁移。
"""
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db import Base

config = context.config

# 从 app 的 settings 取连接串（含 .env 的凭证，不在进程外打印）
def get_url() -> str:
    url = settings.DATABASE_URL
    test_db = os.environ.get("ALEMBIC_TEST_DB")
    if test_db:
        url = url.rsplit("/", 1)[0] + "/" + test_db
    return url

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_impl="postgresql",
        compare_type=True,
        render_as_batch=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(get_url(), poolclass=NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
