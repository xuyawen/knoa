"""add llm_call table

Revision ID: u14llmcall
Revises: u13errorevent
Create Date: 2026-07-31

LLM 调用日志表：调用日志页「模型调用」tab 数据源。每次 LLM 请求
（stream_chat/chat/tool_call）经 capture_llm_call 异步写入，记模型/类型/调用方/
耗时/token/状态/错误/响应截断预览，供系统管理-调用日志页浏览检索。
"""
from alembic import op
import sqlalchemy as sa

revision = 'u14llmcall'
down_revision = 'u13errorevent'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'llm_call',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('request_type', sa.String(length=32), nullable=False),
        sa.Column('caller', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='success'),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('tokens_in', sa.Integer(), nullable=True),
        sa.Column('tokens_out', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('preview', sa.String(length=500), nullable=True),
        sa.Column('rid', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_llm_call_created_at'), 'llm_call', ['created_at'], unique=False)
    op.create_index(op.f('ix_llm_call_request_type'), 'llm_call', ['request_type'], unique=False)
    op.create_index(op.f('ix_llm_call_rid'), 'llm_call', ['rid'], unique=False)
    op.create_index(op.f('ix_llm_call_status'), 'llm_call', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_llm_call_status'), table_name='llm_call')
    op.drop_index(op.f('ix_llm_call_rid'), table_name='llm_call')
    op.drop_index(op.f('ix_llm_call_request_type'), table_name='llm_call')
    op.drop_index(op.f('ix_llm_call_created_at'), table_name='llm_call')
    op.drop_table('llm_call')
