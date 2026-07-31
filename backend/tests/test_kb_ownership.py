"""知识库归属部门限制：建库强制本部门 + 授权子树约束。

覆盖场景：
- 非超管建库自动归属本部门 + 归属部门默认 view 授权
- 非超管无部门 → 拒绝建库
- 非超管传 ownerDeptId → 仍归属本部门（忽略入参）
- 超管可跨部门指定归属
- 非超管授权仅限本部门子树
- 超管授权不受限
"""
import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select

from app.db import Department, KBDeptGrant, KnowledgeBase, Role, User
from app.main import app


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _make_user(db_session, *, username: str, role_key: str, dept_id=None) -> User:
    """在 DB 中创建指定角色/部门的用户（密码固定 testpass1）。"""
    role_id = await db_session.scalar(select(Role.id).where(Role.key == role_key))
    u = User(
        username=username,
        password_hash=User.hash_password("testpass1"),
        display_name=username,
        role_id=role_id,
        department_id=dept_id,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


async def _login(client, username: str) -> str:
    r = await client.post("/api/auth/login", json={"username": username, "password": "testpass1"})
    assert r.status_code == 200, f"login {username} failed: {r.text}"
    return r.json()["accessToken"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── 建库归属 ───────────────────────────────────────────────────────────────────


async def test_nonsuper_create_kb_auto_owner_dept(client, db_session):
    """非超管建库：自动归属本部门 + 归属部门获 view 授权。"""
    dept = Department(name="测试部A")
    db_session.add(dept)
    await db_session.commit()
    await db_session.refresh(dept)

    await _make_user(db_session, username="ed_a", role_key="editor", dept_id=dept.id)
    token = await _login(client, "ed_a")

    r = await client.post("/api/knowledge-bases", json={"name": "部门库"}, headers=_auth(token))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["ownerDeptId"] == str(dept.id)
    assert data["ownerDeptName"] == "测试部A"

    # 验证 DB：归属部门 view 授权已写入
    grant = (
        await db_session.execute(
            select(KBDeptGrant).where(
                KBDeptGrant.kb_id == data["id"],
                KBDeptGrant.dept_id == dept.id,
            )
        )
    ).scalar_one_or_none()
    assert grant is not None
    assert grant.level == "view"


async def test_nonsuper_no_dept_cannot_create_kb(client, db_session):
    """非超管无部门 → 拒绝建库。"""
    await _make_user(db_session, username="ed_nodept", role_key="editor", dept_id=None)
    token = await _login(client, "ed_nodept")

    r = await client.post("/api/knowledge-bases", json={"name": "x"}, headers=_auth(token))
    assert r.status_code == 400
    assert "部门" in r.json()["detail"]


async def test_nonsuper_owner_dept_forced_to_own(client, db_session):
    """非超管传 ownerDeptId → 仍归属本部门（入参被忽略）。"""
    dept_a = Department(name="部门A")
    dept_b = Department(name="部门B")
    db_session.add_all([dept_a, dept_b])
    await db_session.commit()
    await db_session.refresh(dept_a)
    await db_session.refresh(dept_b)

    await _make_user(db_session, username="ed_b", role_key="editor", dept_id=dept_a.id)
    token = await _login(client, "ed_b")

    # 尝试指定 dept_b → 应被强制为 dept_a
    r = await client.post(
        "/api/knowledge-bases",
        json={"name": "跨部门库", "ownerDeptId": str(dept_b.id)},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["ownerDeptId"] == str(dept_a.id)


async def test_super_create_kb_explicit_dept(client, db_session):
    """超管可跨部门指定归属。"""
    dept = Department(name="目标部")
    db_session.add(dept)
    await db_session.commit()
    await db_session.refresh(dept)

    # admin/admin123 由 conftest _ensure_admin 创建
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = r.json()["accessToken"]

    r = await client.post(
        "/api/knowledge-bases",
        json={"name": "超管跨部门库", "ownerDeptId": str(dept.id)},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["ownerDeptId"] == str(dept.id)
    assert r.json()["ownerDeptName"] == "目标部"


# ─── 授权子树约束 ─────────────────────────────────────────────────────────────────


async def test_nonsuper_grant_restricted_to_subtree(client, db_session):
    """非超管 KB admin 只能授权给本部门子树，不能授权给无关部门。"""
    dept_own = Department(name="本部")
    dept_other = Department(name="外部门")
    db_session.add_all([dept_own, dept_other])
    await db_session.commit()
    await db_session.refresh(dept_own)
    await db_session.refresh(dept_other)

    u = await _make_user(db_session, username="ed_grant", role_key="editor", dept_id=dept_own.id)
    # 手动建库并给该用户 admin 权限（模拟已有库）
    kb = KnowledgeBase(id="kb_granttest", name="授权测试库", icon="📚", owner_dept_id=dept_own.id)
    db_session.add(kb)
    await db_session.flush()
    from app.db import KBPermission
    db_session.add(KBPermission(kb_id="kb_granttest", user_id=u.id, level="admin"))
    await db_session.commit()

    token = await _login(client, "ed_grant")

    # 授权给外部门 → 403
    r = await client.put(
        "/api/knowledge-bases/kb_granttest/dept-grants",
        json={"grants": [{"deptId": str(dept_other.id), "level": "view"}]},
        headers=_auth(token),
    )
    assert r.status_code == 403, f"应拒绝跨部门授权: {r.text}"

    # 授权给本部门 → 200
    r = await client.put(
        "/api/knowledge-bases/kb_granttest/dept-grants",
        json={"grants": [{"deptId": str(dept_own.id), "level": "edit"}]},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text


async def test_super_grant_unrestricted(client, db_session):
    """超管授权不受子树限制。"""
    dept_x = Department(name="任意部")
    db_session.add(dept_x)
    await db_session.commit()
    await db_session.refresh(dept_x)

    kb = KnowledgeBase(id="kb_supergrant", name="超管授权库", icon="📚")
    db_session.add(kb)
    await db_session.commit()

    r = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = r.json()["accessToken"]

    r = await client.put(
        "/api/knowledge-bases/kb_supergrant/dept-grants",
        json={"grants": [{"deptId": str(dept_x.id), "level": "admin"}]},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
