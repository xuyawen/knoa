"""一次性把「策展版」跨境电商知识图谱写入 kg_node / kg_edge。

为什么是策展版而非 LLM 抽取：
    Agnes 推理模型的非流式 content 恒为空、流式 content 也被 reasoning 挤掉，
    结构化 JSON 抽取不稳定（属 P6 KG 回填待攻坚项）。为让 Graph 页在 P4 即可
    真实浏览/筛选/导出，这里注入一份领域真实的策展图谱（与项目 markdown 种子
    同源——都是「真实领域内容、作者整理」而非伪造 UI 数字）。后续 P6 的 LLM
    抽取会在此基础上增量补全。

运行：python -m app.data.seed_graph
"""
import asyncio
import logging

from sqlalchemy import func, select

from app.config import settings
from app.core.rag.embeddings import EmbeddingModel
from app.database import AsyncSessionLocal, init_db
from app.db import DocChunk, Document, KGEdge, KGNode, KnowledgeBase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_graph")

# (label, type, kb_id) — 真实领域概念，按业务域归到对应知识库
NODES: list[tuple[str, str, str]] = [
    # 合规政策
    ("账户健康", "指标", "compliance"),
    ("封号申诉", "流程", "compliance"),
    ("知识产权", "政策", "compliance"),
    ("侵权投诉", "事件", "compliance"),
    ("绩效指标", "指标", "compliance"),
    ("二审", "流程", "compliance"),
    # 广告运营
    ("PPC广告", "功能", "ads"),
    ("关键词竞价", "流程", "ads"),
    ("ACOS", "指标", "ads"),
    ("否定关键词", "策略", "ads"),
    ("广告排名", "指标", "ads"),
    ("展示型广告", "功能", "ads"),
    # 物流仓储
    ("FBA头程", "流程", "logistics"),
    ("海外仓", "功能", "logistics"),
    ("海运", "物流", "logistics"),
    ("空运", "物流", "logistics"),
    ("入库上架", "流程", "logistics"),
    ("尾程配送", "物流", "logistics"),
    # 选品策略
    ("蓝海选品", "策略", "selection"),
    ("市场调研", "流程", "selection"),
    ("竞品分析", "流程", "selection"),
    ("差评率", "指标", "selection"),
    ("新品开发", "流程", "selection"),
    ("刚需品", "概念", "selection"),
    # 客户服务
    ("售后退款", "流程", "service"),
    ("退换货", "流程", "service"),
    ("Review管理", "策略", "service"),
    ("邮件营销", "功能", "service"),
    ("客户留存", "指标", "service"),
    ("差评安抚", "策略", "service"),
]

# (from_label, to_label, relation, kb_id)
EDGES: list[tuple[str, str, str, str]] = [
    ("侵权投诉", "账户健康", "影响", "compliance"),
    ("封号申诉", "账户健康", "恢复", "compliance"),
    ("知识产权", "侵权投诉", "关联", "compliance"),
    ("绩效指标", "账户健康", "决定", "compliance"),
    ("二审", "封号申诉", "属于", "compliance"),
    ("关键词竞价", "广告排名", "决定", "ads"),
    ("ACOS", "PPC广告", "衡量", "ads"),
    ("否定关键词", "PPC广告", "优化", "ads"),
    ("展示型广告", "PPC广告", "属于", "ads"),
    ("海运", "FBA头程", "属于", "logistics"),
    ("空运", "FBA头程", "属于", "logistics"),
    ("FBA头程", "海外仓", "经", "logistics"),
    ("海外仓", "尾程配送", "经", "logistics"),
    ("入库上架", "海外仓", "属于", "logistics"),
    ("市场调研", "蓝海选品", "支撑", "selection"),
    ("竞品分析", "蓝海选品", "支撑", "selection"),
    ("差评率", "新品开发", "影响", "selection"),
    ("刚需品", "蓝海选品", "属于", "selection"),
    ("退换货", "售后退款", "包含", "service"),
    ("Review管理", "客户留存", "影响", "service"),
    ("差评安抚", "Review管理", "属于", "service"),
    ("邮件营销", "客户留存", "促进", "service"),
    # 跨域关联
    ("账户健康", "客户留存", "关联", "compliance"),
    ("FBA头程", "退换货", "影响", "logistics"),
    ("PPC广告", "蓝海选品", "利好", "ads"),
]


async def main():
    await init_db()
    embedder = EmbeddingModel(settings.EMBEDDING_MODEL)

    async with AsyncSessionLocal() as db:
        # 每个 KB 取一个真实 chunk 作为节点 chunk_id（FK 约束）
        kb_chunk: dict[str, object] = {}
        for kb_id, in (await db.execute(select(KnowledgeBase.id))).all():
            cid = (
                await db.execute(
                    select(DocChunk.id)
                    .join(Document, Document.id == DocChunk.document_id)
                    .where(Document.kb_id == kb_id)
                    .limit(1)
                )
            ).scalar()
            if cid:
                kb_chunk[kb_id] = cid

        existing = set(
            (r.label, r.kb_id)
            for r in (await db.execute(select(KGNode.label, KGNode.kb_id))).all()
        )

        # 批量向量化（保证 label 与 embedding 一一对应）
        to_insert = [(lbl, kb) for lbl, _, kb in NODES if (lbl, kb) not in existing]
        if to_insert:
            embs = await embedder.embed([lbl for lbl, _ in to_insert])
            for (lbl, kb), emb in zip(to_insert, embs, strict=True):
                cid = kb_chunk.get(kb)
                if not cid:
                    continue
                db.add(
                    KGNode(
                        kb_id=kb,
                        label=lbl,
                        type=next((t for l, t, k in NODES if l == lbl and k == kb), None),
                        chunk_id=cid,
                        embedding=emb,
                    )
                )
            await db.flush()

        existing_edges = set(
            (r.from_label, r.to_label, r.relation, r.kb_id)
            for r in (
                await db.execute(
                    select(KGEdge.from_label, KGEdge.to_label, KGEdge.relation, KGEdge.kb_id)
                )
            ).all()
        )
        # 边端点须落在本 KB 已存在（含本次新插入）的节点上
        valid_nodes = existing | set(to_insert)
        new_edges = 0
        for f, t, rel, kb in EDGES:
            if (f, t, rel, kb) in existing_edges:
                continue
            if (f, kb) not in valid_nodes or (t, kb) not in valid_nodes:
                continue  # 只连本 KB 已存在节点
            db.add(KGEdge(kb_id=kb, from_label=f, to_label=t, relation=rel))
            new_edges += 1

        await db.commit()
        total_nodes = (await db.execute(select(func.count()).select_from(KGNode))).scalar() or 0
        total_edges = (await db.execute(select(func.count()).select_from(KGEdge))).scalar() or 0
        logger.info("图谱种子完成：+%d 节点, +%d 边；kg_node=%d, kg_edge=%d",
                    len(to_insert), new_edges, total_nodes, total_edges)


def _kb_of(label: str) -> str:
    for l, _, kb in NODES:
        if l == label:
            return kb
    return ""


if __name__ == "__main__":
    asyncio.run(main())
