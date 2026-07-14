"""知识图谱（Graph RAG）— Postgres 图存储 + LLM 抽取 + 图遍历检索增强。

为什么不接 Neo4j：
    本环境起不了 Neo4j server（无 Docker / 无二进制），故用 Postgres 的
    kg_node / kg_edge 两张表存图，复用项目已有的 JSONB + numpy 余弦方案做语义匹配。
    结构留好接口，将来真有 Neo4j 可直接替换实现而不动调用方。

LLM 只在「建图时（摄入）」用一次抽取实体/关系；
「检索时」纯确定性向量匹配（问题向量 vs 实体向量），不调 LLM，
既快又能在 LLM 降级时照常工作（这是和 Mem0 不同的取舍：记忆靠 LLM 抽取，
图谱检索靠向量召回，二者互补）。
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm.base import LLMProvider
from app.core.rag.embeddings import EmbeddingModel
from app.db import DocChunk, Document, KGEdge, KGNode

logger = logging.getLogger(__name__)


def _cosine(a: list[float], b: list[float]) -> float:
    """两个向量的余弦相似度（numpy，与 Mem0 同方案）。"""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _extract_json(text: str):
    """从 LLM 的自由文本里抠出第一个 JSON 对象/数组（容错）。"""
    try:
        return json.loads(text)
    except Exception:
        pass
    # 去 ```json ``` 围栏
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    opens = [i for i, ch in enumerate(cleaned) if ch in "{["]
    if not opens:
        return None
    start = min(opens)
    depth = 0
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start : i + 1])
                except Exception:
                    return None
    return None


def _coerce_graph(obj) -> dict:
    """容错解析 LLM 返回的图结构：支持裸对象 / 数组 / 带 ```json 围栏 / 包装对象。"""
    if isinstance(obj, str):
        obj = _extract_json(obj)
    if isinstance(obj, list):
        # 顶层数组视为实体列表（LLM 偷懒省略外层包裹时的兜底）
        return {"entities": obj, "relations": []}
    if not isinstance(obj, dict):
        return {"entities": [], "relations": []}
    entities = []
    for k in ("entities", "nodes", "entity", "node"):
        if isinstance(obj.get(k), list):
            entities = obj[k]
            break
    relations = []
    for k in ("relations", "edges", "relation", "edge"):
        if isinstance(obj.get(k), list):
            relations = obj[k]
            break
    return {"entities": entities, "relations": relations}


_GRAPH_EXTRACT_PROMPT = """你是一个知识图谱抽取器。请从给定文档中抽取实体（节点）和它们之间的关系（边）。

要求：
- 实体：跨境电商运营知识中的关键概念/对象，如政策名、物流方式、费用项、流程步骤、平台功能等。
- 关系：实体之间的有向关联，如 "A 属于 B"、"A 导致 B"、"A 需要 B"、"A 影响 B"。
- 只抽取文档中明确出现的，不要臆造。
- 实体 label 用简短中文短语；type 标注类别（如 政策/物流/费用/流程/功能）。

输出严格 JSON，格式：
{
  "entities": [{"label": "实体名", "type": "类别"}],
  "relations": [{"from": "起点实体", "to": "终点实体", "relation": "关系描述"}]
}"""


class GraphStore:
    """知识图谱存储 + 检索（Postgres 图，无需 Neo4j）。"""

    def __init__(self, llm: LLMProvider | None = None, embedder: EmbeddingModel | None = None):
        self.llm = llm
        self.embedder = embedder

    # ------------------------------------------------------------------
    # 建图（摄入时调用）
    # ------------------------------------------------------------------
    async def extract(
        self,
        kb_id: str,
        doc_title: str,
        chunks: Sequence[dict],
        db: AsyncSession,
    ) -> None:
        """从一篇文档的 chunks 中抽取实体/关系并写入图。任何一步失败都静默跳过。"""
        if not chunks:
            return
        # 拼文本喂给 LLM（截断，避免超长）
        text = "\n\n".join(
            f"[chunk {c.get('index', i)}] {c.get('content', '')}"
            for i, c in enumerate(chunks)
        )[:6000]
        try:
            raw = await self.llm.chat(
                [
                    {"role": "system", "content": _GRAPH_EXTRACT_PROMPT},
                    {"role": "user", "content": f"文档标题：{doc_title}\n\n文档内容：\n{text}"},
                ],
                temperature=0.0,
            )
        except Exception as e:
            logger.warning("graph extract LLM failed (skip graph for doc %s): %s", doc_title, e)
            return

        graph = _coerce_graph(raw)
        entities = graph["entities"]
        relations = graph["relations"]
        if not entities:
            return

        # 去重：本 KB 已存在的实体 label 不再插（保留首次出现的 chunk）
        existing_labels = set(
            row.label
            for row in (await db.execute(select(KGNode.label).where(KGNode.kb_id == kb_id)))
            .scalars()
            .all()
        )
        existing_edges = set(
            (r.from_label, r.to_label, r.relation)
            for r in (
                await db.execute(
                    select(KGEdge.from_label, KGEdge.to_label, KGEdge.relation).where(
                        KGEdge.kb_id == kb_id
                    )
                )
            )
            .all()
        )

        # 只保留有 label 的实体，再批量向量化（保证 entities 与 embeddings 一一对应）
        valid = [
            (e, str(e.get("label", "")).strip())
            for e in entities
            if str(e.get("label", "")).strip()
        ]
        if not valid:
            return
        labels = [lbl for _, lbl in valid]
        try:
            embeddings = await self.embedder.embed(labels)
        except Exception as e:
            logger.warning("graph embed failed (skip graph for doc %s): %s", doc_title, e)
            return

        inserted_nodes = 0
        for (ent, label), emb in zip(valid, embeddings, strict=True):
            if label in existing_labels:
                continue
            chunk_id = self._locate_chunk(label, chunks)
            db.add(
                KGNode(
                    kb_id=kb_id,
                    label=label,
                    type=str(ent.get("type", "")).strip() or None,
                    chunk_id=chunk_id,
                    embedding=emb,
                )
            )
            existing_labels.add(label)
            inserted_nodes += 1

        # 关系（边）：起止实体都须是本 KB 已知节点，且这条边未存在
        inserted_edges = 0
        for rel in relations:
            f = str(rel.get("from", "")).strip()
            t = str(rel.get("to", "")).strip()
            r = str(rel.get("relation", "")).strip()
            if not (f and t and r):
                continue
            # 仅当两端都在本 KB 实体集合里才建边（保持图连通性）
            if f not in existing_labels or t not in existing_labels:
                continue
            if (f, t, r) in existing_edges:
                continue
            db.add(KGEdge(kb_id=kb_id, from_label=f, to_label=t, relation=r))
            existing_edges.add((f, t, r))
            inserted_edges += 1

        if inserted_nodes or inserted_edges:
            await db.flush()
        logger.info("graph extract doc=%s: +%d nodes, +%d edges", doc_title, inserted_nodes, inserted_edges)

    async def delete_by_doc(
        self, db: AsyncSession, kb_id: str, chunk_ids: list
    ) -> None:
        """删除某文档关联的图谱节点（按 chunk_id 归属）。

        删除文档时调用：先取该文档全部 chunk_id，再清掉引用这些
        chunk 的 kg_node。kg_edge 以 label 为键（非 chunk_id），
        删除节点后检索阶段靠「种子节点存在性」自然隔离，无需级联删边。
        """
        if not chunk_ids:
            return
        await db.execute(
            delete(KGNode).where(KGNode.kb_id == kb_id, KGNode.chunk_id.in_(chunk_ids))
        )
        await db.flush()

    @staticmethod
    def _locate_chunk(label: str, chunks: Sequence[dict]):
        """把实体映射回它首次出现的 chunk（内容包含该 label 的即归属）。"""
        for c in chunks:
            if label in (c.get("content") or ""):
                return c.get("chunk_id")
        return chunks[0].get("chunk_id")

    # ------------------------------------------------------------------
    # 检索（问答时调用）
    # ------------------------------------------------------------------
    async def retrieve_related_chunks(
        self,
        question: str,
        kb_id: str,
        db: AsyncSession,
        top_k: int = 5,
    ) -> list[dict]:
        """图感知检索：问题向量 → 命中实体节点 → 1 跳邻居 → 收集相关 chunk。

        全程纯确定性计算，不调 LLM，即使 LLM/向量降级也能靠已有图谱工作。
        """
        # 1) 取本 KB 全部节点
        nodes = (
            await db.execute(select(KGNode).where(KGNode.kb_id == kb_id))
        ).scalars().all()
        if not nodes:
            return []

        # 2) 问题向量，与节点向量做余弦，挑最相关的作为种子实体
        try:
            q_emb = await self.embedder.embed_query(question)
        except Exception as e:
            logger.warning("graph retrieve embed failed (skip): %s", e)
            return []

        scored = sorted(
            ((_cosine(n.embedding, q_emb), n) for n in nodes),
            key=lambda x: x[0],
            reverse=True,
        )
        # 相似度够高的直接当种子；若一个都没有（问法偏门），兜底取 top_k 最相关
        seed_labels = [n.label for s, n in scored if s >= 0.55][:top_k]
        if not seed_labels:
            seed_labels = [n.label for _, n in scored[:top_k]]

        seed_set = set(seed_labels)
        # 3) 1 跳扩展：沿关系边把邻居也拉进来
        if seed_set:
            edges = (
                await db.execute(select(KGEdge).where(KGEdge.kb_id == kb_id))
            ).scalars().all()
            for e in edges:
                if e.from_label in seed_set:
                    seed_set.add(e.to_label)
                if e.to_label in seed_set:
                    seed_set.add(e.from_label)

        # 4) 收集这些实体对应的 chunk_id（去重，保序）
        node_by_label = {n.label: n for n in nodes if n.label in seed_set}
        chunk_ids: list = []
        seen: set = set()
        for label in seed_set:
            n = node_by_label.get(label)
            if n and n.chunk_id not in seen:
                chunk_ids.append(n.chunk_id)
                seen.add(n.chunk_id)
        if not chunk_ids:
            return []

        # 5) 取 chunk 内容 + 文档标题（一次 join 查询）
        rows = (
            await db.execute(
                select(DocChunk, Document.title)
                .join(Document, Document.id == DocChunk.document_id)
                .where(DocChunk.id.in_(chunk_ids))
            )
        ).all()
        by_id = {c.id: (c, title) for c, title in rows}
        out: list[dict] = []
        for cid in chunk_ids:
            item = by_id.get(cid)
            if not item:
                continue
            c, title = item
            out.append(
                {
                    "chunk_id": str(c.id),
                    "kb": c.kb_id,
                    "title": title or c.kb_id,
                    "snippet": c.content[:300],
                    "content": c.content,
                    "confidence": 0.7,
                    "source_type": "graph",
                }
            )
        return out[:top_k]
