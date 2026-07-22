"""create operation_log & announcement tables (P1: 业务统计根数据源)

Revision ID: p1analytics
Revises: p0docfields
Create Date: 2026-07-21 23:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'p1analytics'
down_revision: Union[str, Sequence[str], None] = 'p0docfields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """建操作日志 / 公告两表（幂等，与 init_db 的 create_all 任一路先跑都不冲突）。"""
    op.execute(text("""
        CREATE TABLE IF NOT EXISTS operation_log (
            id UUID PRIMARY KEY,
            user_id VARCHAR(36),
            display_name VARCHAR(80),
            action VARCHAR(20) NOT NULL,
            related_doc_id VARCHAR(36),
            detail VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_operation_log_user_id ON operation_log(user_id)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_operation_log_action ON operation_log(action)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_operation_log_related_doc_id ON operation_log(related_doc_id)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_operation_log_created_at ON operation_log(created_at)"))

    op.execute(text("""
        CREATE TABLE IF NOT EXISTS announcement (
            id UUID PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            level VARCHAR(20) NOT NULL DEFAULT 'info',
            pinned BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_announcement_created_at ON announcement(created_at)"))


def downgrade() -> None:
    """回滚：删两表（含索引）。"""
    op.execute(text("DROP TABLE IF EXISTS announcement"))
    op.execute(text("DROP TABLE IF EXISTS operation_log"))
