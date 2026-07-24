"""KB 默认严格隔离：为每个无权限记录的遗留知识库补 owner 权限

Revision ID: u5kbstrict
Revises: u4roles
Create Date: 2026-07-24 18:00:00.000000

决策：知识库默认改为严格隔离（每个库仅创建者/被授权者可见可写）。
历史库此前无任何 kb_permission 记录、对全体已登录用户开放。本迁移为
每个"孤儿库"（无权限记录）补一条 owner 权限（level='admin'）：

  - 优先取该库文档的统一上传人（出现次数最多的 uploader_id）作为 owner；
  - 若库内无文档或上传人各异，兜底取内置 admin 用户。

回填后，security.py 的三处访问控制（get_accessible_kb_ids /
get_kb_permission_level / get_knowledge_bases）因每个库都至少有一条权限
记录而自动进入严格隔离语义，无需改动访问代码。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = 'u5kbstrict'
down_revision: Union[str, Sequence[str], None] = 'u4roles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if 'knowledge_base' not in insp.get_table_names() or 'kb_permission' not in insp.get_table_names():
        return

    # 内置 admin 用户（按角色 key），作为无人认领库的 owner 兜底
    admin_id = bind.execute(
        text(
            "SELECT u.id FROM app_user u JOIN roles r ON r.id = u.role_id "
            "WHERE r.key = 'admin' ORDER BY u.created_at LIMIT 1"
        )
    ).scalar()

    # 找出没有任何 kb_permission 记录的遗留库
    orphan_kbs = bind.execute(
        text(
            "SELECT kb.id FROM knowledge_base kb "
            "WHERE NOT EXISTS (SELECT 1 FROM kb_permission p WHERE p.kb_id = kb.id)"
        )
    ).fetchall()

    for (kb_id,) in orphan_kbs:
        # 取该库文档出现次数最多的上传人作为 owner
        owner = bind.execute(
            text(
                "SELECT uploader_id FROM document WHERE kb_id = :kid "
                "GROUP BY uploader_id ORDER BY count(*) DESC LIMIT 1"
            ),
            {"kid": kb_id},
        ).scalar()
        if not owner:
            owner = admin_id
        if not owner:
            continue  # 极端情况：既无文档也无 admin，跳过
        bind.execute(
            text(
                "INSERT INTO kb_permission (id, kb_id, user_id, level, created_at) "
                "VALUES (gen_random_uuid(), :kid, :uid, 'admin', now())"
            ),
            {"kid": kb_id, "uid": owner},
        )


def downgrade() -> None:
    # 数据回填类迁移，downgrade 仅能还原为"开放默认"语义：清空全部库级权限。
    # 注意：此操作同时会删掉应用运行时新建库的 owner 记录，仅用于回退本迁移，
    # 生产请勿随意 downgrade。
    bind = op.get_bind()
    insp = inspect(bind)
    if 'kb_permission' in insp.get_table_names():
        bind.execute(text("DELETE FROM kb_permission"))
