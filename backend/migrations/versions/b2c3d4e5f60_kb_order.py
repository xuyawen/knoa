"""知识库拖拽排序字段

Revision ID: b2c3d4e5f60
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14 13:45:00.000000

前端知识库列表支持拖拽排序，后端按 `order` 整型列持久化顺序。
order 是 SQL 保留字，列名必须用双引号包裹，否则 PG 解析报错。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f60'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(text('ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS "order" INTEGER NOT NULL DEFAULT 0'))
    # 按创建时间给已有库赋序，保持当前列表顺序不变
    op.execute(text(
        'UPDATE knowledge_base kb SET "order" = sub.rn '
        'FROM (SELECT id, ROW_NUMBER() OVER (ORDER BY created_at) AS rn '
        'FROM knowledge_base) sub WHERE kb.id = sub.id'
    ))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(text('ALTER TABLE knowledge_base DROP COLUMN IF EXISTS "order"'))
