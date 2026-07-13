"""检索数学单测：摄入(切分 + 向量化) → HybridRetriever(numpy 余弦 + BM25 + RRF)。

用 FakeEmbedder 生成确定性向量，验证「词重叠」能让正确 chunk 排到第一位。
"""
import uuid

import pytest

from app.core.rag.ingestor import DocumentIngester
from app.core.rag.retriever import HybridRetriever
from app.db import KnowledgeBase

from tests._fakes import FakeEmbedder


async def _make_kb(db, name="retrieval-kb"):
    kb_id = f"kb_{uuid.uuid4().hex[:8]}"
    db.add(KnowledgeBase(id=kb_id, name=name, icon="📚"))
    await db.commit()
    return kb_id


async def test_retrieval_ranks_relevant_chunk_first(db_session):
    kb_id = await _make_kb(db_session)
    ingester = DocumentIngester(FakeEmbedder())
    # 摄入两篇主题不同的文档（内容需 >50 字，否则被 chunker 丢弃）
    await ingester.ingest_text(
        kb_id,
        "退款政策",
        "# 退款政策\n我们在用户收到商品之日起 7 天内支持无理由退款。"
        "申请入口位于「我的订单」页面，点击对应订单的「申请退款」按钮，"
        "填写原因后提交，款项将在 3-5 个工作日内原路退回。跨境订单需先完成清关。",
        db_session,
    )
    await ingester.ingest_text(
        kb_id,
        "物流时效",
        "# 物流时效\n海外仓发货的商品一般 3-5 个工作日送达，大促或节假日可能顺延。"
        "国内仓现货通常 48 小时内出库，用户可在「我的订单」中实时追踪物流节点。",
        db_session,
    )

    retriever = HybridRetriever(FakeEmbedder(), db_session, rrf_k=60)
    results = await retriever.retrieve("怎么申请退款", kb_id, top_k=3)
    assert results, "检索应返回结果"
    # 退款相关 chunk 排第一
    assert "退款" in results[0]["content"], results[0]["content"]
    assert results[0]["title"] == "退款政策"
