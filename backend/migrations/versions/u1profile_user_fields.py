"""用户档案字段：email / department / employee_id

Revision ID: u1profile
Revises: p8schema
Create Date: 2026-07-22 16:00:00.000000

app_user 增加邮箱、部门、工号三列，供用户管理界面维护。
均为nullable，存量用户与种子用户无需回填。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'u1profile'
down_revision: Union[str, Sequence[str], None] = 'p8schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('app_user', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('app_user', sa.Column('department', sa.String(length=100), nullable=True))
    op.add_column('app_user', sa.Column('employee_id', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('app_user', 'employee_id')
    op.drop_column('app_user', 'department')
    op.drop_column('app_user', 'email')
