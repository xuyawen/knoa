"""add knowledge_base.owner_dept_id

Revision ID: c1d2e3f4a5b6
Revises: a066de20b6f1
Create Date: 2026-07-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'a066de20b6f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 知识库归属部门（库级隔离的部门维度）。nullable：存量库无归属部门，
    # 由超管后续指派或保持空（空 = 仅超管及显式授权者可见，配合 fail-close）。
    op.add_column('knowledge_base', sa.Column('owner_dept_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_knowledge_base_owner_dept_id_department',
        'knowledge_base', 'department',
        ['owner_dept_id'], ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_knowledge_base_owner_dept_id_department', 'knowledge_base', type_='foreignkey')
    op.drop_column('knowledge_base', 'owner_dept_id')
