"""app_user 部门外键化：department 文本列 → department_id 外键（部门权限真相源）

Revision ID: u9userdept
Revises: u8chunkscope
Create Date: 2026-07-26 18:00:00.000000

部门级文档权限（scope=department）需要可靠地回答「用户属于哪个部门（id）」，
但 app_user.department 历史上是与 department 表脱节的自由文本，无法参与
`user.department_id == document.department_id` 这类判定。本迁移一次性改干净：

  - 新增 app_user.department_id UUID 外键 → department(id)，作为唯一真相源；
  - 按名回填：既有自由文本 department 匹配 department.name 的，落对应 id（匹配不上留 NULL）；
  - 删除 app_user.department 文本列（显示名改由后端按 id 从 department 表解析）。

顺序约束：先加列 → 回填 → 加外键约束（保证已回填值合法）→ 建索引 → 删文本列。
ADD COLUMN/INDEX IF NOT EXISTS 幂等；外键约束用 DO 块判重，兼容 init_db(create_all)。
downgrade 尽力恢复文本列（按 id 反查部门名），但自由文本原值无法无损还原。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'u9userdept'
down_revision: Union[str, Sequence[str], None] = 'u8chunkscope'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS department_id UUID")
    # 按名回填：自由文本部门匹配 department.name → 落对应 id（匹配不上留 NULL）
    op.execute(
        "UPDATE app_user u SET department_id = d.id FROM department d "
        "WHERE u.department = d.name"
    )
    # 回填后再加外键约束，确保已落值全部合法（DO 块判重，幂等）
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_app_user_department_id') THEN "
        "ALTER TABLE app_user ADD CONSTRAINT fk_app_user_department_id "
        "FOREIGN KEY (department_id) REFERENCES department(id); "
        "END IF; END $$;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_app_user_department_id ON app_user (department_id)"
    )
    op.execute("ALTER TABLE app_user DROP COLUMN IF EXISTS department")


def downgrade() -> None:
    op.execute("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS department VARCHAR(100)")
    # 尽力按 id 反查部门名回填文本列（自由文本原值已不可恢复）
    op.execute(
        "UPDATE app_user u SET department = d.name FROM department d "
        "WHERE u.department_id = d.id"
    )
    op.execute("DROP INDEX IF EXISTS ix_app_user_department_id")
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_app_user_department_id') THEN "
        "ALTER TABLE app_user DROP CONSTRAINT fk_app_user_department_id; "
        "END IF; END $$;"
    )
    op.execute("ALTER TABLE app_user DROP COLUMN IF EXISTS department_id")
