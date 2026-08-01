"""error_event add elapsed_ms

Revision ID: u17errelapsed
Revises: u16errreqbody
Create Date: 2026-08-01

错误事件表加 elapsed_ms 列（Integer, nullable）：记录请求耗时（毫秒），
后端中间件从 elapsed 换算，前端从 performance.now() 差值换算。
"""
from alembic import op
import sqlalchemy as sa

revision = 'u17errelapsed'
down_revision = 'u16errreqbody'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('error_event', sa.Column('elapsed_ms', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('error_event', 'elapsed_ms')
