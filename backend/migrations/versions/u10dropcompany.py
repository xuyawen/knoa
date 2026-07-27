"""移除文档级 scope 的 'company' 档，与 'public' 合并

Revision ID: u10dropcompany
Revises: u9userdept
Create Date: 2026-07-27 19:00:00.000000

'company' 与 'public' 在可见性语义上完全等价（均归入 SCOPE_PUBLIC_LIKE，
全员可见），且系统无外部用户角色，二者无实质差异。本迁移将历史数据中
scope='company' 的文档及其冗余 chunk 收敛为 'public'，随后代码层删除
'company' 档（security.SCOPE_PUBLIC_LIKE、documents 路由校验、前端下拉）。

数据收敛幂等：已为 public 的行不受影响；无 company 行时为空操作。
"""

from typing import Sequence, Union

from alembic import op


revision: str = 'u10dropcompany'
down_revision: Union[str, Sequence[str], None] = 'u9userdept'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 历史 company 文档收敛为 public（行为不变，仅去重档位）
    op.execute("UPDATE document SET scope = 'public' WHERE scope = 'company'")
    op.execute("UPDATE doc_chunk SET scope = 'public' WHERE scope = 'company'")


def downgrade() -> None:
    # 数据已不可逆收敛（原 company 行无法与 public 区分），downgrade 不回滚数据，
    # 仅保留此空操作以免 alembic 降版时报错。
    pass
