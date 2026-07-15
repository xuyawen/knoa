"""聊天消息多模态附件列

Revision ID: fd46be01a5dc
Revises: b2c3d4e5f60
Create Date: 2026-07-15 18:30:00.000000

问答支持图片/音视频上传（一期仅 image），ChatMessage 新增 attachments JSONB 列
存回显数据（kind/mimeType/dataB64/name），由 /api/ask 的 files 落库写入。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'fd46be01a5dc'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(text(
        'ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS attachments JSONB'
    ))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(text(
        'ALTER TABLE chat_message DROP COLUMN IF EXISTS attachments'
    ))
