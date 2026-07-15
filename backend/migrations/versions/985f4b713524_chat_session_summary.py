"""对话滚动摘要列

Revision ID: 985f4b713524
Revises: fd46be01a5dc
Create Date: 2026-07-15 20:15:00.000000

长会话上下文压缩：ChatSession 新增 summary(滚动摘要文本) 与
summarized_count(已纳入摘要的历史消息边界，避免重复摘要)。
由 agent._roll_summary 后台异步维护，注入 LLM system prompt。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '985f4b713524'
down_revision: Union[str, Sequence[str], None] = 'fd46be01a5dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(text(
        'ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS summary TEXT'
    ))
    op.execute(text(
        'ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS summarized_count INTEGER NOT NULL DEFAULT 0'
    ))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(text(
        'ALTER TABLE chat_session DROP COLUMN IF EXISTS summarized_count'
    ))
    op.execute(text(
        'ALTER TABLE chat_session DROP COLUMN IF EXISTS summary'
    ))
