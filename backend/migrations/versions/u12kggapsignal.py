"""add kg_gap_signal table

Revision ID: u12kggapsignal
Revises: u11kbdeptgrant
Create Date: 2026-07-26

知识缺口信号表：问答时图谱无命中 → 记录 gap，驱动文档补充。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'u12kggapsignal'
down_revision = 'u11kbdeptgrant'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'kg_gap_signal',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('kb_id', sa.String(length=50), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['kb_id'], ['knowledge_base.id']),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_kg_gap_signal_kb_id'), 'kg_gap_signal', ['kb_id'], unique=False)
    op.create_index(op.f('ix_kg_gap_signal_user_id'), 'kg_gap_signal', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_kg_gap_signal_user_id'), table_name='kg_gap_signal')
    op.drop_index(op.f('ix_kg_gap_signal_kb_id'), table_name='kg_gap_signal')
    op.drop_table('kg_gap_signal')
