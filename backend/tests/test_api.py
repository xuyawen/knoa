"""API 冒烟：健康检查、鉴权登录、知识库 CRUD、文档上传契约。

无需真实 LLM/Embedding：上传端点已在 conftest 被替换为 FakeGraph/FakeEmbedder，
因此 document upload 的「解析 → 摄入 → 向量化」链路可无 key 跑通。

HTTP 客户端用 httpx.AsyncClient + ASGITransport：让 app 跑在「与测试
同一个 asyncio 事件循环」里。这样 app 内 get_db 打开的 asyncpg 连接
与测试 fixture 的 db_session 始终绑定同一 loop，从根本上消除
TestClient（独立线程/loop）带来的「another operation is in progress /
attached to a different loop」等异步连接错乱。
"""
import httpx
from httpx import ASGITransport

import pytest
import pytest_asyncio

from app.main import app


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _token(client):
    r = await client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert r.status_code == 200, r.text
    # 注意：响应模型是 CamelModel，JSON 键为 accessToken
    return r.json()["accessToken"]


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_auth_login_and_me(client):
    token = await _token(client)
    r = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


async def test_kb_crud(client):
    token = await _token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/knowledge-bases",
        json={"name": "冒烟测试库", "description": "pytest"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    kb_id = r.json()["id"]
    # 列表里能查到刚建的库（CamelModel 输出键为 knowledgeBases）
    lst = (await client.get("/api/knowledge-bases", headers=h)).json()
    assert any(x["id"] == kb_id for x in lst["knowledgeBases"])


async def test_document_upload_and_status(client):
    token = await _token(client)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/knowledge-bases", json={"name": "上传库"}, headers=h
    )
    kb_id = r.json()["id"]
    try:
        # 缺 content/content_b64 → 422（契约校验，不触达摄入）
        bad = await client.post(
            f"/api/knowledge-bases/{kb_id}/documents",
            json={"filename": "x.md"},
            headers=h,
        )
        assert bad.status_code == 422

        # 正常上传（解析 → 摄入 → 向量化，全部走 FakeEmbedder/FakeGraph）
        ok = await client.post(
            f"/api/knowledge-bases/{kb_id}/documents",
            json={
                "filename": "refund.md",
                "content": "# 退款政策\n我们支持 7 天无理由退款，申请入口在「我的订单」。",
            },
            headers=h,
        )
        assert ok.status_code == 201, ok.text
        doc = ok.json()
        assert doc["status"] == "待复核"
        docs = (await client.get(
            f"/api/knowledge-bases/{kb_id}/documents", headers=h
        )).json()
        assert len(docs) == 1 and docs[0]["title"] == "退款政策"
    finally:
        await client.delete(f"/api/knowledge-bases/{kb_id}", headers=h)
