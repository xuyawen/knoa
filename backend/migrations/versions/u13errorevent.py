"""add error_event table

Revision ID: u13errorevent
Revises: d2e3f4a5b6c7
Create Date: 2026-07-31

错误事件表：错误管理页数据源。后端 HTTP 4xx/5xx（observability 中间件）与
前端上报（/api/events）经 capture_error 异步写入，供系统管理-错误管理页浏览检索。
"""
from alembic import op
import sqlalchemy as sa

revision = 'u13errorevent'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'error_event',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('level', sa.String(length=16), nullable=False, server_default='error'),
        sa.Column('method', sa.String(length=10), nullable=True),
        sa.Column('path', sa.String(length=500), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('rid', sa.String(length=32), nullable=True),
        sa.Column('etype', sa.String(length=64), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('stack', sa.Text(), nullable=True),
        sa.Column('ip', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=300), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_error_event_created_at'), 'error_event', ['created_at'], unique=False)
    op.create_index(op.f('ix_error_event_source'), 'error_event', ['source'], unique=False)
    op.create_index(op.f('ix_error_event_status_code'), 'error_event', ['status_code'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_error_event_status_code'), table_name='error_event')
    op.drop_index(op.f('ix_error_event_source'), table_name='error_event')
    op.drop_index(op.f('ix_error_event_created_at'), table_name='error_event')
    op.drop_table('error_event')
