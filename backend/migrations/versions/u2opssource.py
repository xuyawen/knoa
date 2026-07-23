"""operation_log 增加 source_count 列（知识缺口榜数据源）

Revision ID: u2opssource
Revises: u1profile
Create Date: 2026-07-23 11:00:00.000000

问答/搜索埋点记录检索命中的来源片段数，用于聚合「知识缺口」（高频提问但零命中）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'u2opssource'
down_revision: Union[str, Sequence[str], None] = 'u1profile'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'operation_log',
        sa.Column('source_count', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('operation_log', 'source_count')
