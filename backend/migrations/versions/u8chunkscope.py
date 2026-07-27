"""doc_chunk 冗余文档级权限字段：scope/uploader_id/department_id（scope 补全）

Revision ID: u8chunkscope
Revises: u7thinksteps
Create Date: 2026-07-26 16:00:00.000000

检索层（pgvector 内存混合 / ES）需按当前用户可见性过滤私有文档，但 chunk 表
此前只有 kb_id，无法区分 private。本迁移给 doc_chunk 冗余 document 的三个字段：

  - scope        权限范围（private/department/company/public），检索过滤主键
  - uploader_id  上传者（private 文档「仅本人可见」判定用）
  - department_id 部门（P1 部门数据链启用后做部门级判定，本期先冗余）

回填：从 document 表按 document_id join 复制既有值，历史 chunk 全部归位为
对应文档的 scope（种子文档默认 public）。新增 (kb_id, scope) 复合索引加速
「按库 + 权限范围」的检索过滤。

ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS 幂等，兼容
init_db(create_all) 先建列建索引的场景。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'u8chunkscope'
down_revision: Union[str, Sequence[str], None] = 'u7thinksteps'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS scope VARCHAR(20) NOT NULL DEFAULT 'public'"
    )
    op.execute("ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS uploader_id UUID")
    op.execute("ALTER TABLE doc_chunk ADD COLUMN IF NOT EXISTS department_id UUID")
    # 回填：既有 chunk 按其文档的 scope/上传者/部门归位（种子文档默认 public）
    op.execute(
        "UPDATE doc_chunk c SET scope = d.scope, uploader_id = d.uploader_id, "
        "department_id = d.department_id FROM document d WHERE c.document_id = d.id"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_doc_chunk_kb_scope ON doc_chunk (kb_id, scope)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_doc_chunk_kb_scope")
    op.execute("ALTER TABLE doc_chunk DROP COLUMN IF EXISTS department_id")
    op.execute("ALTER TABLE doc_chunk DROP COLUMN IF EXISTS uploader_id")
    op.execute("ALTER TABLE doc_chunk DROP COLUMN IF EXISTS scope")
