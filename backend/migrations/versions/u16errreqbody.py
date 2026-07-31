"""error_event add request_body

Revision ID: u16errreqbody
Revises: u15trendingdept
Create Date: 2026-08-01

错误事件表加 request_body 列（Text, nullable）：前端上报 HTTP 错误时携带请求体参数
（POST/PUT/PATCH 请求截断到 2000 字符），方便排查「请求了什么被拒绝」。
"""
from alembic import op
import sqlalchemy as sa

revision = 'u16errreqbody'
down_revision = 'u15trendingdept'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('error_event', sa.Column('request_body', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('error_event', 'request_body')
