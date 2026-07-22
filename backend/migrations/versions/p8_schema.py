"""P8 schema: user settings columns + announcement read tracking

- app_user.preferred_model (用户偏好问答模型)
- app_user.tts_enabled (语音播报开关)
- user_announcement_read (通知已读记录)

Revision ID: p8schema
Revises: p2fixuploaderfk
Create Date: 2026-07-22 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'p8schema'
down_revision: Union[str, Sequence[str], None] = 'p2fixuploaderfk'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # app_user 加两列：幂等，列已存在则跳过
    op.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'app_user' AND column_name = 'preferred_model'
            ) THEN
                ALTER TABLE app_user ADD COLUMN preferred_model VARCHAR(64);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'app_user' AND column_name = 'tts_enabled'
            ) THEN
                ALTER TABLE app_user ADD COLUMN tts_enabled BOOLEAN NOT NULL DEFAULT false;
            END IF;
        END $$;
    """))

    # 通知已读表：幂等建表
    op.execute(text("""
        CREATE TABLE IF NOT EXISTS user_announcement_read (
            user_id UUID NOT NULL,
            announcement_id UUID NOT NULL,
            read_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, announcement_id),
            FOREIGN KEY (user_id) REFERENCES app_user(id),
            FOREIGN KEY (announcement_id) REFERENCES announcement(id)
        )
    """))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS user_announcement_read"))
    op.execute(text("ALTER TABLE app_user DROP COLUMN IF EXISTS tts_enabled"))
    op.execute(text("ALTER TABLE app_user DROP COLUMN IF EXISTS preferred_model"))
