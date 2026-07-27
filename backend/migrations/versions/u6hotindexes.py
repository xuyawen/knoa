"""高频查询列补索引：document.kb_id、doc_chunk.document_id（L6）

Revision ID: u6hotindexes
Revises: u5kbstrict
Create Date: 2026-07-26 10:00:00.000000

文档列表按 kb_id 过滤、删除文档/级联删库按 document_id 清 chunk，
均为高频等值查询；无索引时随数据量增长退化为全表扫描。
IF NOT EXISTS 幂等，兼容 init_db(create_all) 先建索引的场景。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'u6hotindexes'
down_revision: Union[str, Sequence[str], None] = 'u5kbstrict'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE INDEX IF NOT EXISTS ix_document_kb_id ON document (kb_id)')
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_doc_chunk_document_id ON doc_chunk (document_id)'
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ix_doc_chunk_document_id')
    op.execute('DROP INDEX IF EXISTS ix_document_kb_id')
