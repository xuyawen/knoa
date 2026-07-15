import asyncio
import logging
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=settings.APP_ENV == "development")
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def _run_alembic_upgrade() -> None:
    """子进程跑 `alembic upgrade head`（用项目 venv 的 python）。

    走子进程而不是在本进程内调 alembic API，是为了避免与 FastAPI
    已运行的事件循环嵌套 asyncio.run（env.py 的 run_migrations_online
    内部会 asyncio.run，嵌套会抛 RuntimeError）。子进程有独立 loop，干净。
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "upgrade", "head",
        cwd=backend_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade failed (rc={proc.returncode}): "
            f"{(err or out or b'').decode('utf-8', 'ignore')[:500]}"
        )


async def _migrate_columns(conn) -> None:
    """幂等补列：create_all 不会给已存在的表追加新列，这里补上新增字段。

    用 PostgreSQL 的 `ADD COLUMN IF NOT EXISTS`，重复执行零副作用。
    Document 在方案 A（延迟摄入）后新增了 original_filename / file_size /
    reviewed_at / reviewed_by 四个字段，老库升级时靠它补齐，无需手写一次性脚本。
    """
    cols = [
        ("original_filename", "VARCHAR(255)"),
        ("file_size", "INTEGER"),
        ("reviewed_at", "TIMESTAMP WITH TIME ZONE"),
        ("reviewed_by", "VARCHAR(100)"),
    ]
    for name, typ in cols:
        await conn.execute(
            text(f"ALTER TABLE document ADD COLUMN IF NOT EXISTS {name} {typ}")
        )
    # knowledge_base 排序字段（前端拖拽排序用）；order 是保留字，列名需引号
    kb_cols = [('"order"', "INTEGER NOT NULL DEFAULT 0")]
    for name, typ in kb_cols:
        await conn.execute(
            text(f"ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS {name} {typ}")
        )
    # 聊天消息多模态附件（一期仅 image JSONB 回显数据）
    chat_cols = [("attachments", "JSONB")]
    for name, typ in chat_cols:
        await conn.execute(
            text(f"ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS {name} {typ}")
        )


async def init_db():
    """建表：优先走 Alembic 版本化迁移；装不上/连不上时回退 create_all。

    - 生产 / Docker：alembic 已装且库已 stamp，跑 `upgrade head` 增量迁移。
    - 本地 venv 没装 alembic、或数据库尚未 stamp：捕获异常后
      用 Base.metadata.create_all 兜底，保证开发能直接起（dev 友好）。
    - 无论哪条路径，最后都跑 `_migrate_columns` 幂等补列：
      项目尚未落地 alembic 迁移文件，新增列靠它兜底，老库升级不丢字段。
    """
    try:
        await _run_alembic_upgrade()
        logger.info("init_db: alembic upgrade head done")
    except Exception as e:          # alembic 缺失 / 库未 stamp / 连接失败等
        logger.warning("init_db: alembic unavailable, fallback create_all: %s", e)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    # 幂等补列（create_all 不给已有表补列；alembic 无迁移时也兜底）
    async with engine.begin() as conn:
        await _migrate_columns(conn)
