"""app_user 增加 model_prefs JSONB 列（模型配置服务端真值）

Revision ID: u3modelprefs
Revises: u2opssource
Create Date: 2026-07-24 14:00:00.000000

模型配置（温度/TopP/最大长度/TopK/联网/来源数/provider/人设/思考/简洁）
从前端 localStorage 收口到服务端；模型选择(name)走已有的 preferred_model 列，
其余 10 项走 model_prefs JSONB。前端不再持久化这些配置。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'u3modelprefs'
down_revision: Union[str, Sequence[str], None] = 'u2opssource'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'app_user',
        sa.Column('model_prefs', postgresql.JSONB(), nullable=True, server_default='{}'),
    )


def downgrade() -> None:
    op.drop_column('app_user', 'model_prefs')
