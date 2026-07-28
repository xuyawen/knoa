"""新增 kb_dept_grant 表（库级部门授权）

Revision ID: u11kbdeptgrant
Revises: u10dropcompany
Create Date: 2025-01-20 10:00:00.000000

新增 kb_dept_grant 表，用于存储"知识库 → 部门"的授权记录。
授权给某部门后，该部门及其所有下级部门的用户继承该权限。
合并语义为"个人显式优先"：kb_permission 有记录则用个人的，
无个人记录时取部门祖先链上的最高授权。

旧表 kb_permission 完全不动、不迁数据。回滚只需 drop 新表。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'u11kbdeptgrant'
down_revision: Union[str, Sequence[str], None] = 'u10dropcompany'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'kb_dept_grant',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('kb_id', sa.String(50), sa.ForeignKey('knowledge_base.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('dept_id', UUID(as_uuid=True), sa.ForeignKey('department.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('level', sa.String(20), nullable=False, server_default='view'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('kb_id', 'dept_id', name='uq_kb_dept'),
    )


def downgrade() -> None:
    op.drop_table('kb_dept_grant')
