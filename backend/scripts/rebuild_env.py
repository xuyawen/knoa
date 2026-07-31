"""重建本地环境：8 部门 + 每部门 10 员工 + 每部门独立 KB + 部门授权 + admin。

前提：已 DROP 并 init_db() 建表（本脚本会清掉 init_db 自动播种的默认部门，
重建为 8 个目标部门；admin 按 .env 凭据补建，保留账号）。

跑法（必须在 backend/ 目录下，以读到 .env）：
    cd X:/workspace/knoa/backend
    .venv/Scripts/python.exe scripts/rebuild_env.py
"""
import asyncio
import sys
import uuid

sys.path.insert(0, r"X:\workspace\knoa\backend")

from sqlalchemy import select, text

from app.config import settings
from app.database import AsyncSessionLocal, _seed_roles
from app.db import (
    Department,
    KBDeptGrant,
    KnowledgeBase,
    Role,
    User,
)

# (部门中文名, 描述, kb key, icon)
DEPTS = [
    ("运营", "跨境业务与店铺运营（亚马逊 / TikTok Shop 等）", "ops", "Store"),
    ("财务", "税务 · 支付 · 资金结算与合规", "finance", "Landmark"),
    ("产品", "选品 · 上架 · 增长与广告", "product", "Sparkles"),
    ("实施", "系统集成 · 平台对接 · API 落地", "impl", "Plug"),
    ("物流", "头程 · 履约 · 仓储与退货", "logistics", "Package"),
    ("合规", "风控 · 政策 · 资质与监管", "compliance", "Shield"),
    ("客服", "售后 · 工单 · 评价与体验", "service", "Headset"),
    ("人事", "招聘 · 绩效 · 组织与培训", "hr", "Users"),
]
EMP_PASSWORD = "q123321."
EMP_PER_DEPT = 10


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # 0) 确保内置角色存在（admin / editor / viewer，按 key 解析，不硬编码 UUID）
        await _seed_roles()
        roles = {r.key: r.id for r in (await db.execute(select(Role))).scalars().all()}

        # 1) 清空 init_db 自动播种的默认部门（当前 user 为空，无外键残留）
        await db.execute(text("DELETE FROM department"))

        # 2) 建 8 个目标部门 + 各自独立 KB
        dept_map: dict[str, uuid.UUID] = {}
        kb_map: dict[str, str] = {}
        for idx, (name, desc, key, icon) in enumerate(DEPTS, start=1):
            d = Department(name=name, description=desc, sort_order=idx)
            db.add(d)
            await db.flush()
            dept_map[name] = d.id
            kb_id = f"kb_{key}"
            db.add(
                KnowledgeBase(
                    id=kb_id,
                    name=f"{name}知识库",
                    icon=icon,
                    description=desc,
                    owner_dept_id=d.id,
                )
            )
            await db.flush()  # 必须立即落库，后续 KBDeptGrant 的 FK 才能满足
            kb_map[name] = kb_id

        # 3) 每部门 10 名员工（第 1 人 editor 负责人，其余 viewer）
        for name, _desc, key, _icon in DEPTS:
            dept_id = dept_map[name]
            for i in range(1, EMP_PER_DEPT + 1):
                role_key = "editor" if i == 1 else "viewer"
                username = f"{key}{i:02d}"
                display = f"{name}部-{'负责人' if i == 1 else f'员工{i}'}"
                db.add(
                    User(
                        username=username,
                        password_hash=User.hash_password(EMP_PASSWORD),
                        display_name=display,
                        role_id=roles[role_key],
                        department_id=dept_id,
                        is_active=True,
                        email=f"{username}@knoa.local",
                    )
                )

        # 4) 部门授权：每个部门对其专属 KB 拥有 edit 级（部门内全员可见，editor 可编辑）
        for name, _desc, _key, _icon in DEPTS:
            db.add(
                KBDeptGrant(
                    kb_id=kb_map[name],
                    dept_id=dept_map[name],
                    level="edit",
                )
            )

        # 5) admin：始终确保存在（保留 admin 账号，按 .env 凭据 upsert，
        #    不依赖起服务；字段对齐 main.py 的 lifespan 播种逻辑，避免重复创建冲突）
        admin = await db.scalar(
            select(User).where(User.username == settings.ADMIN_USERNAME)
        )
        if admin is None:
            db.add(
                User(
                    username=settings.ADMIN_USERNAME,
                    password_hash=User.hash_password(settings.ADMIN_PASSWORD),
                    display_name=settings.ADMIN_DISPLAY_NAME,
                    role_id=roles["admin"],
                    is_active=True,
                    email=settings.ADMIN_EMAIL,
                    employee_id=settings.ADMIN_EMPLOYEE_ID,
                )
            )

        await db.commit()

    print("[rebuild] done:")
    print(f"  departments : {len(DEPTS)}")
    print(f"  employees  : {len(DEPTS) * EMP_PER_DEPT} (pwd={EMP_PASSWORD})")
    print(f"  kb         : {len(DEPTS)} (kb_<key>)")
    print(f"  admin      : {settings.ADMIN_USERNAME} (from .env)")


if __name__ == "__main__":
    asyncio.run(main())
