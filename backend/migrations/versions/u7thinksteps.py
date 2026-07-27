"""chat_message 加 thinking_steps 列（持久化 Agentic RAG 决策链，L7）

Revision ID: u7thinksteps
Revises: u6hotindexes
Create Date: 2026-07-27 12:30:00.000000

历史会话回显"思考过程"需要把决策链落库。新部署由 init_db(create_all) 直接建列；
本迁移仅补已存在库。DO 块幂等，重复执行不报错。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'u7thinksteps'
down_revision: Union[str, Sequence[str], None] = 'u6hotindexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS ("
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='chat_message' AND column_name='thinking_steps'"
        ") THEN ALTER TABLE chat_message ADD COLUMN thinking_steps JSONB; END IF; END $$;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE chat_message DROP COLUMN IF EXISTS thinking_steps")
