"""引入角色管理：roles / role_permission 表 + app_user.role_id 外键

Revision ID: u4roles
Revises: u3modelprefs
Create Date: 2026-07-24 16:30:00.000000

- 新建 roles（角色定义）与 role_permission（角色→权限关联）两张表
- app_user 增加 role_id 外键，回填自旧 role 字符串列，随后删除 role 列
- 内置角色 admin/editor/viewer 及默认权限在此写入（幂等，key 冲突跳过）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'u4roles'
down_revision: Union[str, Sequence[str], None] = 'u3modelprefs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 内置角色固定 UUID，保证回填可确定映射
BUILTIN = {
    'admin':  '11111111-1111-1111-1111-111111111111',
    'editor': '22222222-2222-2222-2222-222222222222',
    'viewer': '33333333-3333-3333-3333-333333333333',
}
BUILTIN_PERMS = {
    'admin':  ['kb_view', 'doc_upload', 'doc_edit', 'doc_delete', 'ai_qa',
               'graph_manage', 'user_manage', 'sys_settings'],
    'editor': ['kb_view', 'doc_upload', 'doc_edit', 'ai_qa', 'graph_manage'],
    'viewer': ['kb_view', 'ai_qa'],
}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1) 创建 roles 表（若尚未存在，兼容 create_all 已建的场景）
    if 'roles' not in existing_tables:
        op.create_table(
            'roles',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('key', sa.String(50), nullable=False),
            sa.Column('name', sa.String(50), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_builtin', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_roles_key', 'roles', ['key'], unique=True)

    # 2) 创建 role_permission 表
    if 'role_permission' not in existing_tables:
        op.create_table(
            'role_permission',
            sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('permission_key', sa.String(50), nullable=False),
            sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('role_id', 'permission_key'),
        )

    # 3) app_user 增加 role_id 列（先可空，回填后再置 NOT NULL）
    #    同步建外键 + 命名索引，与模型 (ForeignKey("roles.id"), index=True) 对齐，
    #    否则 `alembic check` 会报角色表/索引漂移。
    cols = [c['name'] for c in insp.get_columns('app_user')]
    if 'role_id' not in cols:
        op.add_column(
            'app_user',
            sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key('app_user_role_id_fkey', 'app_user', 'roles',
                              ['role_id'], ['id'])
        op.create_index('ix_app_user_role_id', 'app_user', ['role_id'])

    # 4) 写入内置角色（幂等：key 冲突跳过）
    for key, rid in BUILTIN.items():
        bind.execute(sa.text(
            "INSERT INTO roles (id, key, name, description, is_builtin, sort_order, created_at) "
            "VALUES (:id, :key, :name, :desc, true, :ord, now()) "
            "ON CONFLICT (key) DO NOTHING"
        ), {"id": rid, "key": key, "name": key.capitalize(), "desc": None, "ord": 0})

    # 5) 写入内置角色权限（幂等）
    for key, rid in BUILTIN.items():
        for pk in BUILTIN_PERMS[key]:
            bind.execute(sa.text(
                "INSERT INTO role_permission (role_id, permission_key) "
                "VALUES (:rid, :pk) ON CONFLICT DO NOTHING"
            ), {"rid": rid, "pk": pk})

    # 6) 回填 app_user.role_id（仅当旧 role 列存在）
    if 'role' in cols:
        for key, rid in BUILTIN.items():
            bind.execute(sa.text(
                "UPDATE app_user SET role_id = :rid WHERE role = :key AND role_id IS NULL"
            ), {"rid": rid, "pk": pk, "key": key})
        # 其余未命中（理论上无）默认归 viewer
        bind.execute(sa.text(
            "UPDATE app_user SET role_id = :rid WHERE role_id IS NULL"
        ), {"rid": BUILTIN['viewer']})

    # 7) role_id 置 NOT NULL
    op.alter_column('app_user', 'role_id', existing_type=postgresql.UUID(as_uuid=True),
                    nullable=False)

    # 8) 删除旧 role 列
    if 'role' in cols:
        op.drop_column('app_user', 'role')


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = [c['name'] for c in insp.get_columns('app_user')]
    if 'role' not in cols:
        op.add_column(
            'app_user',
            sa.Column('role', sa.String(20), nullable=False, server_default='viewer'),
        )
        bind.execute(sa.text(
            "UPDATE app_user SET role = r.key FROM roles r WHERE r.id = app_user.role_id"
        ))
    op.drop_column('app_user', 'role_id')
    op.drop_table('role_permission')
    op.drop_table('roles')
