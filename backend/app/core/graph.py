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
import time
from collections.abc import Sequence

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm.base import LLMProvider
from app.core.rag.embeddings import EmbeddingModel
from app.db import DocChunk, Document, KGEdge, KGNode

logger = logging.getLogger(__name__)

# 图检索缓存：每个 kb 的节点/边按 kb_id 缓存（TTL），避免每个请求全表加载。
# 写入侧（extract / delete_by_doc）会主动失效对应 kb 的缓存，保证一致性。
_GRAPH_CACHE: dict[str, dict] = {}
_GRAPH_TTL = 60  # 秒


def _graph_cache_key(kb_id: str) -> str:
    return f"g:{kb_id}"


def _invalidate_graph(kb_id: str) -> None:
    _GRAPH_CACHE.pop(_graph_cache_key(kb_id), None)


def _cosine(a: list[float], b: list[float]) -> float:
    """两个向量的余弦相似度（numpy，与 Mem0 同方案）。"""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _extract_json(text: str):
    """从 LLM 的自由文本里抠出 JSON 对象/数组（容错）。

    推理模型（如 Agnes）常把结构化输出塞进 reasoning_content，且中间可能夹带
    草稿 JSON，真正完整的 JSON 在末尾。故优先整体解析，失败则尝试从「最后一个」
    配平 JSON 块提取（推理模型的终版 JSON 通常在最后），再回退到首个块。
    """
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    # 去 ```json ``` 围栏
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    opens = [i for i, ch in enumerate(cleaned) if ch in "{["]
    if not opens:
        return None

    def _match_from(start: int):
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

    # 末位优先（推理模型终版 JSON 在末尾），失败再往前试
    for start in reversed(opens):
        obj = _match_from(start)
        if isinstance(obj, (dict, list)):
            return obj
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
            # 推理模型（Agnes）非流式 chat 的 content 常为空，且 reasoning 会吃掉
            # max_tokens 预算导致 JSON 被截断；故用流式 + 提高 token 上限，
            # 让完整 JSON 落在 content 流里（与非流式问答同一套流式通道）。
            raw = "".join(
                c
                for c in await self._stream_completion(doc_title, text)
            )
        except Exception as e:
            logger.warning("graph extract LLM failed (skip graph for doc %s): %s", doc_title, e)
            return
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
            _invalidate_graph(kb_id)
        logger.info("graph extract doc=%s: +%d nodes, +%d edges", doc_title, inserted_nodes, inserted_edges)

    async def _stream_completion(self, doc_title: str, text: str) -> list[str]:
        """用流式通道拿结构化抽取结果。

        推理模型（Agnes）非流式 chat 的 content 常为空，且 reasoning 会吃掉
        max_tokens 预算把 JSON 截断；流式 + 抬高 token 上限能让完整 JSON 落在
        content 流里（与问答共用同一流式通道）。
        """
        chunks: list[str] = []
        async for piece in self.llm.stream_chat(
            [
                {"role": "system", "content": _GRAPH_EXTRACT_PROMPT},
                {"role": "user", "content": f"文档标题：{doc_title}\n\n文档内容：\n{text}"},
            ],
            temperature=0.0,
            max_tokens=8000,
        ):
            chunks.append(piece)
        return chunks

    async def delete_by_doc(
        self, db: AsyncSession, kb_id: str, chunk_ids: list
    ) -> None:
        """删除某文档关联的图谱节点与边（按 chunk_id 归属）。

        删除文档时调用：先取该文档全部 chunk_id，清掉引用这些
        chunk 的 kg_node；同时级联清理引用这些节点 label 的 kg_edge，
        否则会留下悬空脏边（两端实体已删、边却还在）。
        """
        if not chunk_ids:
            return
        # 边以实体 label 字符串为键引用节点（非 chunk_id），故先取被删节点的 label，
        # 再一并删除 from_label / to_label 命中这些 label 的边。
        labels = (
            await db.execute(
                select(KGNode.label).where(
                    KGNode.kb_id == kb_id, KGNode.chunk_id.in_(chunk_ids)
                )
            )
        ).scalars().all()
        if labels:
            await db.execute(
                delete(KGEdge).where(
                    KGEdge.kb_id == kb_id,
                    (KGEdge.from_label.in_(labels)) | (KGEdge.to_label.in_(labels)),
                )
            )
        await db.execute(
            delete(KGNode).where(KGNode.kb_id == kb_id, KGNode.chunk_id.in_(chunk_ids))
        )
        await db.flush()
        _invalidate_graph(kb_id)

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

        节点/边按 kb_id 缓存（TTL），避免每个请求全表加载；写入侧
        （extract / delete_by_doc）会主动失效对应 kb 的缓存，保证一致性。
        全程纯确定性计算，不调 LLM，即使 LLM/向量降级也能靠已有图谱工作。
        """
        # 1) 取本 KB 节点/边（带 TTL 缓存，避免每请求全表扫描）
        key = _graph_cache_key(kb_id)
        now = time.monotonic()
        entry = _GRAPH_CACHE.get(key)
        if entry and now - entry["ts"] < _GRAPH_TTL:
            node_list = entry["nodes"]
            edge_list = entry["edges"]
        else:
            nodes = (
                await db.execute(select(KGNode).where(KGNode.kb_id == kb_id))
            ).scalars().all()
            if not nodes:
                return []
            edges = (
                await db.execute(select(KGEdge).where(KGEdge.kb_id == kb_id))
            ).scalars().all()
            # 转纯 dict 缓存，避免跨请求复用已过期（detached）的 ORM 对象
            node_list = [
                {"label": n.label, "chunk_id": n.chunk_id, "embedding": n.embedding}
                for n in nodes
                if n.embedding is not None
            ]
            edge_list = [
                {"from_label": e.from_label, "to_label": e.to_label, "relation": e.relation}
                for e in edges
            ]
            _GRAPH_CACHE[key] = {"ts": now, "nodes": node_list, "edges": edge_list}

        # 2) 问题向量，与节点向量做余弦，挑最相关的作为种子实体
        try:
            q_emb = await self.embedder.embed_query(question)
        except Exception as e:
            logger.warning("graph retrieve embed failed (skip): %s", e)
            return []

        scored = sorted(
            ((_cosine(nd["embedding"], q_emb), nd) for nd in node_list),
            key=lambda x: x[0],
            reverse=True,
        )
        # 相似度够高的直接当种子；若一个都没有（问法偏门），兜底取 top_k 最相关
        seed_labels = [nd["label"] for s, nd in scored if s >= 0.55][:top_k]
        if not seed_labels:
            seed_labels = [nd["label"] for _, nd in scored[:top_k]]

        seed_set = set(seed_labels)
        # 3) 1 跳扩展：沿关系边把邻居也拉进来
        if seed_set:
            for e in edge_list:
                if e["from_label"] in seed_set:
                    seed_set.add(e["to_label"])
                if e["to_label"] in seed_set:
                    seed_set.add(e["from_label"])

        # 4) 收集这些实体对应的 chunk_id（去重，保序）
        node_by_label = {nd["label"]: nd for nd in node_list if nd["label"] in seed_set}
        chunk_ids: list = []
        seen: set = set()
        for label in seed_set:
            nd = node_by_label.get(label)
            if nd and nd["chunk_id"] not in seen:
                chunk_ids.append(nd["chunk_id"])
                seen.add(nd["chunk_id"])
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
