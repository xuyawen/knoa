"""chat_session add pinned

Revision ID: u18sessionpin
Revises: u17errelapsed
Create Date: 2026-08-21

会话表加 pinned 列（Boolean, NOT NULL, 默认 false）：侧边栏三点菜单
「置顶」切换，列表排序 pinned 优先、同组内按 updated_at 倒序。
"""
from alembic import op
import sqlalchemy as sa

revision = 'u18sessionpin'
down_revision = 'u17errelapsed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'chat_session',
        sa.Column('pinned', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_column('chat_session', 'pinned')
