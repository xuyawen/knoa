"""问答链路 SSE 端到端（无真实 LLM）：

- conftest 已把 ask 路由的 get_llm/get_embedder/get_redis 替换为替身；
- 走已打补丁的上传端点摄入一篇退款文档（FakeEmbedder，无 key）；
- 验证「检索 → 决策 → 生成 → SSE done」整条链路，断言收到 sources 与 done 事件且回答非空。

同样用 httpx.AsyncClient + ASGITransport，使 app 与测试共用一个事件循环，
避免 asyncpg 连接跨 loop 错乱（见 test_api.py 头部说明）。
"""
import json
import uuid

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from tests._fakes import FakeEmbedder  # noqa: F401  (确保替身可用)


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _token(client):
    r = await client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    return r.json()["accessToken"]


def _parse_sse(text: str) -> list[dict]:
    """解析 SSE：sse-starlette 用 CRLF 分隔事件，且事件间以空行隔开。

    先统一把 \\r\\n 规整成 \\n，再按空行切分，避免 Windows/服务端的
    CRLF 导致 split('\\n\\n') 切不开。
    """
    events: list[dict] = []
    for block in text.replace("\r\n", "\n").strip().split("\n\n"):
        ev: dict = {}
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev["event"] = line[len("event:") :].strip()
            elif line.startswith("data:"):
                ev["data"] = line[len("data:") :].strip()
        if ev:
            events.append(ev)
    return events


async def test_ask_streams_answer(client, db_session):
    token = await _token(client)
    h = {"Authorization": f"Bearer {token}"}
    # 建库（走已打补丁的上传端点摄入，隔离 SSE 测试与上传契约）
    kb_id = (
        await client.post("/api/knowledge-bases", json={"name": "ask-kb"}, headers=h)
    ).json()["id"]
    try:
        # 知识库已由上面的 client.post 建好并提交（与 app 共用同一
        # 测试库、同一 function loop，db_session 这边能见到已提交的 KB，
        # 因此检索/摄入的 FK 自然满足，无需再手动 insert 一遍
        # （否则会因同一 kb_id 重复插入触发唯一约束冲突）。
        from app.core.rag.ingestor import DocumentIngester

        ing = DocumentIngester(FakeEmbedder())
        await ing.ingest_text(
            kb_id,
            "退款政策",
            "# 退款政策\n用户自签收之日起 7 天内可申请无理由退款，"
            "入口在「我的订单」页对应订单的「申请退款」按钮，审核通过后 3-5 个工作日原路退回。",
            db_session,
        )

        r = await client.post(
            "/api/ask",
            json={
                "question": "怎么申请退款",
                "knowledgeBase": kb_id,
                # 真实前端用 UUID 作 sessionId；pipeline 会按 UUID 解析，
                # 传非 UUID 串会触发 badly formed hexadecimal UUID 错误。
                "sessionId": str(uuid.uuid4()),
            },
            headers=h,
        )
        assert r.status_code == 200, r.text
        events = _parse_sse(r.text)
        kinds = [e["event"] for e in events]
        assert "sources" in kinds, events
        assert "done" in kinds, events
        answer = "".join(
            json.loads(e["data"])["content"]
            for e in events
            if e["event"] == "delta"
        )
        assert answer.strip(), "回答不应为空"
    finally:
        await client.delete(f"/api/knowledge-bases/{kb_id}", headers=h)
