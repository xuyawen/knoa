"""一次性脚本：灌入 10 个测试账号，覆盖各种字段场景，方便前端/权限测试。

- 幂等：用户名已存在则跳过，不重复插入。
- 统一密码：test123
- 运行：backend/.venv/Scripts/python.exe scripts/seed_test_users.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func
from app.database import AsyncSessionLocal, _seed_roles
from app.db import Role, User


# 10 个测试账号：覆盖 admin/editor/viewer、启用/停用、
# 邮箱/显示名/部门/工号 缺省、偏好模型、语音播报 等多种场景。
SEED_USERS = [
    {
        "username": "test_admin",
        "display_name": "张明",
        "role": "admin",
        "is_active": True,
        "email": "zhangming@knoa.local",
        "department": "总部",
        "employee_id": "A0002",
    },
    {
        "username": "test_editor",
        "display_name": "李华",
        "role": "editor",
        "is_active": True,
        "email": "lihua@knoa.local",
        "department": "产品部",
        "employee_id": "E0001",
    },
    {
        "username": "test_viewer",
        "display_name": "王芳",
        "role": "viewer",
        "is_active": True,
        "email": "wangfang@knoa.local",
        "department": "市场部",
        "employee_id": "V0001",
    },
    {
        "username": "test_no_email",
        "display_name": "赵雷",
        "role": "viewer",
        "is_active": True,
        "email": None,  # 缺邮箱
        "department": "财务部",
        "employee_id": "V0002",
    },
    {
        "username": "test_no_name",
        "display_name": None,  # 缺显示名
        "role": "editor",
        "is_active": True,
        "email": "noname@knoa.local",
        "department": "运维部",
        "employee_id": None,  # 缺工号
    },
    {
        "username": "test_inactive",
        "display_name": "陈静",
        "role": "viewer",
        "is_active": False,  # 停用
        "email": "chenjing@knoa.local",
        "department": "HR",
        "employee_id": "V0003",
    },
    {
        "username": "test_no_emp",
        "display_name": "孙强",
        "role": "editor",
        "is_active": True,
        "email": "sunqiang@knoa.local",
        "department": "产品部",
        "employee_id": None,  # 缺工号
    },
    {
        "username": "test_no_dept",
        "display_name": "周婷",
        "role": "viewer",
        "is_active": True,
        "email": "zhouting@knoa.local",
        "department": None,  # 缺部门
        "employee_id": "V0004",
    },
    {
        "username": "test_pro_model",
        "display_name": "吴磊",
        "role": "admin",
        "is_active": True,
        "email": "wulei@knoa.local",
        "department": "总部",
        "employee_id": "A0003",
        "preferred_model": "agnes-2.0-pro",  # 指定偏好模型
    },
    {
        "username": "test_tts_on",
        "display_name": "郑爽",
        "role": "viewer",
        "is_active": True,
        "email": "zhengshuang@knoa.local",
        "department": "市场部",
        "employee_id": "V0005",
        "tts_enabled": True,  # 开启语音播报
    },
]

PASSWORD = "test123"


async def main() -> None:
    created = 0
    skipped = 0
    async with AsyncSessionLocal() as session:
        # 确保内置角色已存在（首启可能尚未经应用 lifespan 播种）
        await _seed_roles()
        roles = {
            r.key: r.id
            for r in (await session.execute(select(Role))).scalars().all()
        }
        for u in SEED_USERS:
            exists = await session.scalar(
                select(func.count()).select_from(User).where(User.username == u["username"])
            )
            if exists:
                skipped += 1
                print(f"[skip] {u['username']} 已存在")
                continue
            role_key = u.get("role", "viewer")
            role_id = roles.get(role_key)
            if role_id is None:
                print(f"[warn] {u['username']} 角色 {role_key} 不存在，跳过")
                continue
            session.add(
                User(
                    username=u["username"],
                    password_hash=User.hash_password(PASSWORD),
                    display_name=u.get("display_name"),
                    role_id=role_id,
                    is_active=u.get("is_active", True),
                    preferred_model=u.get("preferred_model"),
                    tts_enabled=u.get("tts_enabled", False),
                    email=u.get("email"),
                    department=u.get("department"),
                    employee_id=u.get("employee_id"),
                )
            )
            created += 1
            print(f"[add ] {u['username']} ({role_key}, active={u.get('is_active', True)})")
        await session.commit()

    print(f"\n完成：新增 {created} 个，跳过 {skipped} 个。统一密码：{PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
