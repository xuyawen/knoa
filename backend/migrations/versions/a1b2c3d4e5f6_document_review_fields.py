"""document 审核留痕字段（方案 A 延迟摄入）

Revision ID: a1b2c3d4e5f6
Revises: eb70aefd7b19
Create Date: 2026-07-14 11:55:00.000000

方案 A（延迟摄入）后，上传只落库不切分，新增字段：
- original_filename：原始文件名（列表/详情展示）
- file_size：原始字节大小（展示真实体积，而非解析后文本长度）
- reviewed_at / reviewed_by：approve / reject 时写入的审核留痕
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'eb70aefd7b19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('document', sa.Column('original_filename', sa.String(length=255), nullable=True))
    op.add_column('document', sa.Column('file_size', sa.Integer(), nullable=True))
    op.add_column('document', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('document', sa.Column('reviewed_by', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('document', 'reviewed_by')
    op.drop_column('document', 'reviewed_at')
    op.drop_column('document', 'file_size')
    op.drop_column('document', 'original_filename')
