"""trending add department_id

Revision ID: u15trendingdept
Revises: u14llmcall
Create Date: 2026-07-26

热搜加部门维度：department_id（nullable FK → department.id, ON DELETE SET NULL）。
计数按搜索者所属部门分桶，展示侧按用户可见部门子树聚合，避免跨部门热搜泄漏。
"""
from alembic import op
import sqlalchemy as sa

revision = 'u15trendingdept'
down_revision = 'u14llmcall'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('trending', sa.Column('department_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f('fk_trending_department_id_department'),
        'trending', 'department',
        ['department_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_trending_department_id'), 'trending', ['department_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_trending_department_id'), table_name='trending')
    op.drop_constraint(op.f('fk_trending_department_id_department'), 'trending', type_='foreignkey')
    op.drop_column('trending', 'department_id')
