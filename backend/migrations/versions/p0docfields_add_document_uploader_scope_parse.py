"""add document uploader, scope, parse_status (P0: 真实三要素)

Revision ID: p0docfields
Revises: b66e5634cb56
Create Date: 2026-07-21 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'p0docfields'
down_revision: Union[str, Sequence[str], None] = 'b66e5634cb56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """加文档真实三要素列（幂等，与 database._migrate_columns 兜底一致）。"""
    # ponytail: IF NOT EXISTS 兜底，alembic 与 _migrate_columns 任一路先跑都不冲突
    op.execute(text('ALTER TABLE document ADD COLUMN IF NOT EXISTS uploader_id UUID'))
    op.execute(text("ALTER TABLE document ADD COLUMN IF NOT EXISTS uploader_name VARCHAR(100)"))
    op.execute(text("ALTER TABLE document ADD COLUMN IF NOT EXISTS scope VARCHAR(20) NOT NULL DEFAULT 'public'"))
    op.execute(text("ALTER TABLE document ADD COLUMN IF NOT EXISTS parse_status VARCHAR(20) NOT NULL DEFAULT 'pending'"))


def downgrade() -> None:
    """回滚三要素列。"""
    op.execute(text('ALTER TABLE document DROP COLUMN IF EXISTS parse_status'))
    op.execute(text('ALTER TABLE document DROP COLUMN IF EXISTS scope'))
    op.execute(text('ALTER TABLE document DROP COLUMN IF EXISTS uploader_name'))
    op.execute(text('ALTER TABLE document DROP COLUMN IF EXISTS uploader_id'))
