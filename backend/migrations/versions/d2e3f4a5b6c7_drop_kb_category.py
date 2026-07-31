"""drop knowledge_base.category

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-07-31 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # KB 分类字段已被「归属部门」(owner_dept_id) 完全取代，删除冗余列。
    op.drop_column('knowledge_base', 'category')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('knowledge_base', sa.Column('category', sa.String(50), nullable=True))
