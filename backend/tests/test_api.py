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
import uuid
from httpx import ASGITransport

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.db import DocChunk, Document
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


async def test_upload_pending_then_approve_ingests(client, db_session):
    """方案 A（延迟摄入）端到端验收：

    - 上传：状态=待复核，且此时 DocChunk 必须为 0（未摄入，检索天然隔离）
    - 详情：能拿到解析后的 content_md
    - 审核通过：触发摄入，DocChunk > 0
    - 驳回：状态=已拒绝，DocChunk 仍 0（不摄入）
    - 删除：DocChunk 与 Document 全清
    """
    token = await _token(client)
    h = {"Authorization": f"Bearer {token}"}
    kb_id = (await client.post("/api/knowledge-bases", json={"name": "审核库"}, headers=h)).json()["id"]

    # 1) 上传即落库、不摄入
    up = await client.post(
        f"/api/knowledge-bases/{kb_id}/documents",
        json={
            "filename": "a.md",
            "content": "# A\n这是待审核内容，检索不应命中。"
            "我们需要一段足够长的文本来触发分块逻辑，确保审核通过之后"
            "文档真正进入向量检索库，从而在问答时可以被正确召回并作为引用来源展示。",
        },
        headers=h,
    )
    assert up.status_code == 201, up.text
    doc_id = up.json()["id"]
    assert up.json()["status"] == "待复核"
    n0 = (await db_session.execute(
        select(func.count()).select_from(DocChunk).where(DocChunk.document_id == uuid.UUID(doc_id))
    )).scalar()
    assert n0 == 0, "上传即摄入，违反方案 A（未审核内容会泄漏进检索）"

    # 2) 详情接口拿得到解析全文
    det = (await client.get(f"/api/knowledge-bases/{kb_id}/documents/{doc_id}", headers=h)).json()
    assert "待审核内容" in det["contentMd"]

    # 3) 审核通过 → 触发摄入
    ap = await client.post(f"/api/knowledge-bases/{kb_id}/documents/{doc_id}/approve", headers=h)
    assert ap.status_code == 200, ap.text
    assert ap.json()["status"] == "已审核"
    n1 = (await db_session.execute(
        select(func.count()).select_from(DocChunk).where(DocChunk.document_id == uuid.UUID(doc_id))
    )).scalar()
    assert n1 > 0, "approve 后未摄入"

    # 4) 驳回一条新上传 → 状态已拒绝且无 chunk
    up2 = await client.post(
        f"/api/knowledge-bases/{kb_id}/documents",
        json={"filename": "b.md", "content": "# B\n驳回这条。我们需要足够长的文本来触发分块逻辑，确保驳回路径正确不摄入。"},
        headers=h,
    )
    doc2 = up2.json()["id"]
    rj = await client.post(f"/api/knowledge-bases/{kb_id}/documents/{doc2}/reject", headers=h)
    assert rj.status_code == 200 and rj.json()["status"] == "已拒绝"
    n2 = (await db_session.execute(
        select(func.count()).select_from(DocChunk).where(DocChunk.document_id == uuid.UUID(doc2))
    )).scalar()
    assert n2 == 0, "reject 后不应有 chunk"

    # 5) 删除：chunk 与 Document 全清
    await client.delete(f"/api/knowledge-bases/{kb_id}/documents/{doc_id}", headers=h)
    n3 = (await db_session.execute(
        select(func.count()).select_from(DocChunk).where(DocChunk.document_id == uuid.UUID(doc_id))
    )).scalar()
    gone = await db_session.scalar(select(Document).where(Document.id == uuid.UUID(doc_id)))
    assert n3 == 0
    assert gone is None


async def test_short_document_still_ingested(client, db_session):
    """短文本保护（方案2）：极短但含实质内容的文档审核通过后,
    仍至少产出 1 个 chunk、可被检索命中, 而非被噪声阈值吞掉。
    """
    token = await _token(client)
    h = {"Authorization": f"Bearer {token}"}
    kb_id = (await client.post("/api/knowledge-bases", json={"name": "短文本库"}, headers=h)).json()["id"]
    try:
        # 8 字, 远低于旧版硬编码的 50 阈值
        up = await client.post(
            f"/api/knowledge-bases/{kb_id}/documents",
            json={"filename": "faq.md", "content": "退货期限是30天。"},
            headers=h,
        )
        assert up.status_code == 201, up.text
        doc_id = up.json()["id"]
        assert up.json()["status"] == "待复核"
        # 上传不摄入
        n0 = (await db_session.execute(
            select(func.count()).select_from(DocChunk).where(DocChunk.document_id == uuid.UUID(doc_id))
        )).scalar()
        assert n0 == 0
        # 审核通过 → 即使极短也必须摄入, 否则搜不到
        ap = await client.post(
            f"/api/knowledge-bases/{kb_id}/documents/{doc_id}/approve", headers=h
        )
        assert ap.status_code == 200 and ap.json()["status"] == "已审核"
        n1 = (await db_session.execute(
            select(func.count()).select_from(DocChunk).where(DocChunk.document_id == uuid.UUID(doc_id))
        )).scalar()
        assert n1 >= 1, "短文档被噪声阈值丢弃, 审核后搜不到"
    finally:
        await client.delete(f"/api/knowledge-bases/{kb_id}", headers=h)
