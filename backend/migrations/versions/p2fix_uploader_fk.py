"""add FK document.uploader_id -> app_user.id (P0 drift fix)

The p0docfields migration added the column as a bare UUID without the
ForeignKey("app_user.id") that the ORM model declares. Alembic `check`
flags this as a new upgrade operation, so we attach the constraint here.
Additive & idempotent: the column already exists; we only add the FK.

Revision ID: p2fixuploaderfk
Revises: p1analytics
Create Date: 2026-07-22 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'p2fixuploaderfk'
down_revision: Union[str, Sequence[str], None] = 'p1analytics'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 幂等：仅当约束不存在时再添加，避免重复迁移报已存在
    op.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_document_uploader_id'
                  AND table_name = 'document'
            ) THEN
                ALTER TABLE document
                    ADD CONSTRAINT fk_document_uploader_id
                    FOREIGN KEY (uploader_id) REFERENCES app_user(id);
            END IF;
        END $$;
    """))


def downgrade() -> None:
    op.execute(text("ALTER TABLE document DROP CONSTRAINT IF EXISTS fk_document_uploader_id"))
