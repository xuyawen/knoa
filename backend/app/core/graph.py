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
from app.models.llm_calls import caller_var

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
    except json.JSONDecodeError:
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
                    except json.JSONDecodeError:
                        return None
        return None

    # 末位优先（推理模型终版 JSON 在末尾），失败再往前试
    for start in reversed(opens):
        obj = _match_from(start)
        if isinstance(obj, (dict, list)):
            return obj
    return None


def _coerce_graph(obj) -> dict:
    """容错解析 LLM 返回的图结构：支持裸对象 / 数组 / 带 ```json 围栏 / 包装对象。

    额外容错：部分模型把 entities 输出成字符串数组（["A","B"]）而非对象数组
    （[{"label":"A"}]），这里统一归一化成 {"label": ...} 字典，避免后续
    `e.get("label")` 在 str 上抛 AttributeError（曾导致整条抽取静默失败）。
    """
    if isinstance(obj, str):
        obj = _extract_json(obj)
    if isinstance(obj, list):
        # 顶层数组视为实体列表（LLM 偷懒省略外层包裹时的兜底）
        raw_entities = obj
        raw_relations: list = []
    elif isinstance(obj, dict):
        raw_entities = []
        for k in ("entities", "nodes", "entity", "node"):
            if isinstance(obj.get(k), list):
                raw_entities = obj[k]
                break
        raw_relations = []
        for k in ("relations", "edges", "relation", "edge"):
            if isinstance(obj.get(k), list):
                raw_relations = obj[k]
                break
    else:
        return {"entities": [], "relations": []}

    # 实体归一化：字符串 → {"label": s}；字典 → 原样保留（取 label/type）
    entities = []
    for e in raw_entities:
        if isinstance(e, str):
            s = e.strip()
            if s:
                entities.append({"label": s})
        elif isinstance(e, dict):
            entities.append(e)
        # 其他类型（数字等）忽略

    # 关系归一化：仅保留含 from/to/relation 的字典
    relations = []
    for r in raw_relations:
        if isinstance(r, dict) and ("from" in r or "from_label" in r) and ("to" in r or "to_label" in r):
            relations.append(r)
        # 字符串/其他形态的关系难以可靠解析，best-effort 丢弃

    # 过滤孤立实体：不参与任何关系的节点无图谱价值，丢弃避免视觉噪声
    connected = set()
    for r in relations:
        connected.add((r.get("from") or r.get("from_label") or "").strip())
        connected.add((r.get("to") or r.get("to_label") or "").strip())
    entities = [e for e in entities if e.get("label", "").strip() in connected]

    return {"entities": entities, "relations": relations}


_GRAPH_EXTRACT_PROMPT = """你是一个知识图谱抽取器。请从给定文档中抽取实体（节点）和它们之间的关系（边）。

要求：
- 实体：企业知识中的关键概念/对象（可来自跨境电商、财务、产品、实施等任意业务域），如政策名、流程步骤、费用项、功能模块等。
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
        # 调用方标签：让本次抽图的 LLM 调用在调用日志中标 caller=graph_extract，
        # 便于按调用方排查「抽图静默无产出」类问题（finally reset 不污染后续调用）。
        token = caller_var.set("graph_extract")
        try:
            try:
                # 推理模型（Agnes）非流式 chat 的 content 常为空，且 reasoning 会吃掉
                # max_tokens 预算导致 JSON 被截断；故用流式 + 提高 token 上限，
                # 让完整 JSON 落在 content 流里（与非流式问答同一套流式通道）。
                raw = "".join(
                    c
                    for c in await self._stream_completion(doc_title, text)
                )
            except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort fallback, skip graph build on any LLM failure)
                logger.warning("graph extract LLM failed (skip graph for doc %s): %s", doc_title, e)
                return
        finally:
            caller_var.reset(token)

        graph = _coerce_graph(raw)
        entities = graph["entities"]
        relations = graph["relations"]
        if not entities:
            logger.warning(
                "graph extract: LLM returned no entities (doc=%s, raw_len=%d, head=%r) — skip graph",
                doc_title, len(raw), raw[:120],
            )
            return

        # 去重：本 KB 已存在的实体 label 不再插（保留首次出现的 chunk）
        # 注意：select(KGNode.label).scalars().all() 返回的是标量字符串列表，
        # 不是 KGNode 对象，直接 collect 即可（之前误写 row.label 导致 AttributeError，
        # LLM 抽取链路长期静默失效，图谱节点全靠 curated seed 兜底）。
        existing_labels = set(
            (await db.execute(select(KGNode.label).where(KGNode.kb_id == kb_id)))
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

        # 只保留有 label 的实体
        valid = [
            (e, str(e.get("label", "")).strip())
            for e in entities
            if str(e.get("label", "")).strip()
        ]
        if not valid:
            return
        entity_labels = {lbl for _, lbl in valid}

        # 收集 relations 中引用但未列入 entities、且本库尚不存在的端点 label。
        # LLM 常在关系里引用它忘记列进 entities 的实体；自动补建这些端点，
        # 避免边因端点缺失被跳过、实体落单成孤儿（保留完整信息）。
        endpoint_labels: set[str] = set()
        for rel in relations:
            for key in ("from", "to"):
                lbl = str(rel.get(key, "")).strip()
                if lbl and lbl not in entity_labels and lbl not in existing_labels:
                    endpoint_labels.add(lbl)

        # 实体 + 缺失端点 一次性批量向量化（保证顺序一一对应）
        ep_sorted = sorted(endpoint_labels)
        all_labels = [lbl for _, lbl in valid] + ep_sorted
        try:
            embeddings = await self.embedder.embed(all_labels)
        except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort fallback, skip graph if embedding fails)
            logger.warning("graph embed failed (skip graph for doc %s): %s", doc_title, e)
            return
        entity_embs = embeddings[: len(valid)]
        ep_embs = dict(zip(ep_sorted, embeddings[len(valid):], strict=True))

        inserted_nodes = 0
        new_labels: list[str] = []
        for (ent, label), emb in zip(valid, entity_embs, strict=True):
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
            new_labels.append(label)
            inserted_nodes += 1

        # 补建缺失端点节点（type 未知，仅作为关系枢纽保留连通性）
        for label in ep_sorted:
            if label in existing_labels:
                continue
            chunk_id = self._locate_chunk(label, chunks)
            db.add(
                KGNode(
                    kb_id=kb_id,
                    label=label,
                    type=None,
                    chunk_id=chunk_id,
                    embedding=ep_embs[label],
                )
            )
            existing_labels.add(label)
            new_labels.append(label)
            inserted_nodes += 1

        # 关系（边）：起止实体都须是本 KB 已知节点，且这条边未存在
        inserted_edges = 0
        linked_labels: set[str] = set()
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
            linked_labels.add(f)
            linked_labels.add(t)
            inserted_edges += 1

        # 清理孤儿节点：本轮新建但未挂上任何边的实体
        # （LLM 常在 relations 里引用未列入 entities 的实体名，导致边被跳过、节点落单）
        orphan_labels = [lbl for lbl in new_labels if lbl not in linked_labels]
        if orphan_labels:
            await db.execute(
                delete(KGNode).where(KGNode.kb_id == kb_id, KGNode.label.in_(orphan_labels))
            )
            for lbl in orphan_labels:
                existing_labels.discard(lbl)
            inserted_nodes -= len(orphan_labels)
            logger.info("graph extract doc=%s: pruned %d orphan nodes", doc_title, len(orphan_labels))

        if inserted_nodes or inserted_edges:
            await db.flush()
            _invalidate_graph(kb_id)
        logger.info("graph extract doc=%s: +%d nodes, +%d edges", doc_title, inserted_nodes, inserted_edges)

    async def _stream_completion(self, doc_title: str, text: str) -> list[str]:
        """用流式通道拿结构化抽取结果。

        enable_thinking=False：关闭推理模型的思考链——思考链会吃光 max_tokens
        预算导致 JSON 被截断（生产实测：8000 token 全被思考吃完，0 实体产出）。
        结构化抽取是模式匹配型任务，不需要深度推理，关闭后 token 全部留给 JSON 输出。
        include_reasoning=True 保留作兜底：provider 不支持 enable_thinking 时
        仍能收集 reasoning_content 中的 JSON（_extract_json 容错定位配平 JSON 块）。
        """
        chunks: list[str] = []
        async for piece in self.llm.stream_chat(
            [
                {"role": "system", "content": _GRAPH_EXTRACT_PROMPT},
                {"role": "user", "content": f"文档标题：{doc_title}\n\n文档内容：\n{text}"},
            ],
            temperature=0.0,
            max_tokens=8000,
            include_reasoning=True,
            enable_thinking=False,
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
        # 级联删边可能使其他节点失去最后一条边（如 Z→X 的 X 被删）→ 统一清理落单节点
        await self.prune_isolated_nodes(db, kb_id)
        await db.flush()
        _invalidate_graph(kb_id)

    async def prune_isolated_nodes(self, db: AsyncSession, kb_id: str) -> int:
        """清理本库中无任何边关联的落单节点（度为 0）。

        产生场景：文档删除 / 增量更新级联删边后，对端节点失去最后一条边；
        或 LLM 只抽出了实体未抽出关系。零度节点在图谱中仅为噪点，
        实体内容仍保留在文档 chunk 中，删除不影响检索。
        """
        linked = select(KGEdge.from_label).where(KGEdge.kb_id == kb_id).union(
            select(KGEdge.to_label).where(KGEdge.kb_id == kb_id)
        )
        result = await db.execute(
            delete(KGNode).where(KGNode.kb_id == kb_id, KGNode.label.notin_(linked))
        )
        return result.rowcount or 0

    async def incremental_extract(
        self,
        kb_id: str,
        doc_title: str,
        chunks: Sequence[dict],
        db: AsyncSession,
        old_chunk_ids: list | None = None,
    ) -> None:
        """增量图更新：文档内容变更后 diff 式重抽（而非全量删+重建）。

        逻辑：
        1. 先抽取新实体/关系（复用 extract 的 LLM 调用）
        2. 对比新旧实体集合：
           - 新增实体 → 插入
           - 消失实体 → 检查是否被其他文档引用（chunk_id 属于其他 doc）→ 无引用才删
           - 存续实体 → 不动
        3. 边同理：两端实体都在 → 保留；任一端被删 → 删边

        old_chunk_ids: 该文档旧的 chunk_id 列表（用于判断哪些实体属于这篇文档）。
        """
        if not chunks:
            return
        # 取该文档旧实体（按 old_chunk_ids 归属）
        old_labels: set[str] = set()
        if old_chunk_ids:
            old_labels = set(
                (await db.execute(
                    select(KGNode.label).where(
                        KGNode.kb_id == kb_id, KGNode.chunk_id.in_(old_chunk_ids)
                    )
                )).scalars().all()
            )

        # 抽取新实体（复用 extract 的 LLM + 向量化逻辑，但不写入）
        text = "\n\n".join(
            f"[chunk {c.get('index', i)}] {c.get('content', '')}"
            for i, c in enumerate(chunks)
        )[:6000]
        try:
            raw = "".join(c for c in await self._stream_completion(doc_title, text))
        except Exception as e:  # noqa: BLE001
            logger.warning("incremental extract LLM failed (skip): %s", e)
            return

        graph = _coerce_graph(raw)
        entities = graph["entities"]
        new_labels = {
            str(e.get("label", "")).strip()
            for e in entities
            if str(e.get("label", "")).strip()
        }

        # 消失实体：旧有但新抽未出现
        vanished = old_labels - new_labels
        # 存续实体：新旧都有 → 不动
        # 新增实体：新有但旧无 → 插入（复用 extract 的写入逻辑）

        # 删除消失实体（仅当其 chunk_id 属于本文档，即不被其他文档引用）
        if vanished and old_chunk_ids:
            # 只删属于本文档 chunk 的节点
            deletable = (
                await db.execute(
                    select(KGNode.label).where(
                        KGNode.kb_id == kb_id,
                        KGNode.label.in_(vanished),
                        KGNode.chunk_id.in_(old_chunk_ids),
                    )
                )
            ).scalars().all()
            if deletable:
                await db.execute(
                    delete(KGEdge).where(
                        KGEdge.kb_id == kb_id,
                        (KGEdge.from_label.in_(deletable)) | (KGEdge.to_label.in_(deletable)),
                    )
                )
                await db.execute(
                    delete(KGNode).where(
                        KGNode.kb_id == kb_id,
                        KGNode.label.in_(deletable),
                        KGNode.chunk_id.in_(old_chunk_ids),
                    )
                )

        # 新增实体 + 边：复用 extract（它内部会去重已存在的 label）
        # 先清旧 chunk 归属的节点（让 extract 重新插入更新后的实体）
        if old_chunk_ids:
            await db.execute(
                delete(KGNode).where(KGNode.kb_id == kb_id, KGNode.chunk_id.in_(old_chunk_ids))
            )
        # 调 extract 写入新实体（它会跳过已存在的 label）
        await self.extract(kb_id, doc_title, chunks, db)
        # 消失实体的级联删边可能使其他节点落单 → 统一清理
        await self.prune_isolated_nodes(db, kb_id)
        _invalidate_graph(kb_id)
        logger.info(
            "incremental graph update doc=%s: vanished=%d, new=%d",
            doc_title, len(vanished), len(new_labels - old_labels),
        )

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
    async def _load_graph(self, kb_id: str, db: AsyncSession) -> "tuple[list, list]":
        """取本 KB 的节点/边（带 TTL 缓存，转纯 dict 避免跨请求复用 detached ORM）。

        1 跳检索与多跳推理共用同一份加载逻辑，保证一致性。
        """
        key = _graph_cache_key(kb_id)
        now = time.monotonic()
        entry = _GRAPH_CACHE.get(key)
        if entry and now - entry["ts"] < _GRAPH_TTL:
            return entry["nodes"], entry["edges"]
        nodes = (
            await db.execute(select(KGNode).where(KGNode.kb_id == kb_id))
        ).scalars().all()
        if not nodes:
            return [], []
        edges = (
            await db.execute(select(KGEdge).where(KGEdge.kb_id == kb_id))
        ).scalars().all()
        node_list = [
            {"label": n.label, "type": n.type, "chunk_id": n.chunk_id, "embedding": n.embedding}
            for n in nodes
            if n.embedding is not None
        ]
        edge_list = [
            {"from_label": e.from_label, "to_label": e.to_label, "relation": e.relation}
            for e in edges
        ]
        _GRAPH_CACHE[key] = {"ts": now, "nodes": node_list, "edges": edge_list}
        return node_list, edge_list

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
        # 1) 取本 KB 节点/边（带 TTL 缓存）
        node_list, edge_list = await self._load_graph(kb_id, db)
        if not node_list:
            return []

        # 2) 问题向量，与节点向量做余弦，挑最相关的作为种子实体
        try:
            q_emb = await self.embedder.embed_query(question)
        except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort fallback, skip retrieval if embed fails)
            logger.warning("graph retrieve embed failed (skip): %s", e)
            return []

        scored = sorted(
            ((_cosine(nd["embedding"], q_emb), nd) for nd in node_list),
            key=lambda x: x[0],
            reverse=True,
        )
        # 相似度够高的直接当种子；若一个都没有（问法偏门），兆底取 top_k 最相关
        seed_labels = [nd["label"] for s, nd in scored if s >= 0.55][:top_k]
        if not seed_labels:
            seed_labels = [nd["label"] for _, nd in scored[:top_k]]
        
        # 构建 label → 真实余弦分数的映射（用于置信度）
        score_by_label = {nd["label"]: s for s, nd in scored}
        
        seed_set = set(seed_labels)
        # 3) 1 跳扩展：沿关系边把邻居也拉进来
        neighbor_labels: set[str] = set()
        if seed_set:
            for e in edge_list:
                if e["from_label"] in seed_set and e["to_label"] not in seed_set:
                    neighbor_labels.add(e["to_label"])
                if e["to_label"] in seed_set and e["from_label"] not in seed_set:
                    neighbor_labels.add(e["from_label"])
        seed_set = seed_set | neighbor_labels

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
            # 置信度：找到该 chunk 对应的实体 label，用真实余弦分数
            # 种子实体用原始分数，1 跳邻居用种子最高分 * 0.8 衰减
            conf = 0.5  # 兆底
            for lbl in seed_set:
                nd = node_by_label.get(lbl)
                if nd and nd["chunk_id"] == cid:
                    raw = score_by_label.get(lbl, 0.5)
                    if lbl in neighbor_labels:
                        # 邻居：取种子最高分 * 0.8
                        best_seed = max((score_by_label.get(s, 0) for s in seed_labels), default=0.5)
                        conf = round(best_seed * 0.8, 3)
                    else:
                        conf = round(raw, 3)
                    break
            out.append(
                {
                    "chunk_id": str(c.id),
                    "kb": c.kb_id,
                    "kb_id": c.kb_id,
                    "title": title or c.kb_id,
                    "doc_id": str(c.document_id),
                    "snippet": c.content[:300],
                    "content": c.content,
                    "confidence": conf,
                    "source_type": "graph",
                }
            )
        return out[:top_k]

    async def multi_hop_reason(
        self,
        question: str,
        kb_id: str,
        db: AsyncSession,
        max_hops: int = 2,
        top_chains: int = 8,
    ) -> "tuple[list[str], list[dict]]":
        """多跳推理（Phase 6 §8.5）：问题向量 → 种子实体 → 沿关系边 BFS 多跳
        → 产出可读推理链路文本 + 沿途命中的相关 chunk。

        返回 (chains, chunks)：
        - chains: 形如 "实体A --关系--> 实体B <--关系-- 实体C" 的推理链路列表
        - chunks: 多跳沿途实体对应的 DocChunk  dict（结构同 retrieve_related_chunks）

        与 1 跳检索共享 `_load_graph` 与向量种子逻辑；同样纯确定性、不调 LLM。
        """
        node_list, edge_list = await self._load_graph(kb_id, db)
        if not node_list:
            return [], []

        try:
            q_emb = await self.embedder.embed_query(question)
        except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort fallback, skip reasoning if embed fails)
            logger.warning("graph multihop embed failed (skip): %s", e)
            return [], []

        # 种子实体：问题向量最相关的若干节点
        scored = sorted(
            ((_cosine(nd["embedding"], q_emb), nd) for nd in node_list),
            key=lambda x: x[0],
            reverse=True,
        )
        seeds = [nd["label"] for s, nd in scored if s >= 0.55][: settings.GRAPH_TOP_K]
        if not seeds:
            seeds = [nd["label"] for _, nd in scored[: settings.GRAPH_TOP_K]]
        seed_set = set(seeds)
        score_by_label = {nd["label"]: s for s, nd in scored}

        # 无向邻接表（BFS 双向可达），保留边方向与关系文本
        from collections import deque

        adj: dict[str, list] = {}
        for e in edge_list:
            adj.setdefault(e["from_label"], []).append((e["to_label"], e["relation"], "fwd"))
            adj.setdefault(e["to_label"], []).append((e["from_label"], e["relation"], "bwd"))

        # BFS：记录前驱 + 关系段，便于回溯出完整推理链路
        visited: set = set(seed_set)
        parent: dict[str, "tuple[str, str] | None"] = {lbl: None for lbl in seed_set}
        depth: dict[str, int] = {lbl: 0 for lbl in seed_set}
        q: "deque[str]" = deque(seed_set)
        while q:
            cur = q.popleft()
            if depth[cur] >= max_hops:
                continue
            for nb, rel, tag in adj.get(cur, []):
                if nb in visited:
                    continue
                visited.add(nb)
                # 从 seed 往外走时，链路方向统一写成「起点 --关系--> 终点」；
                # 反向遍历（cur 是 to_label）则写成「起点 <--关系-- 终点」。
                seg = f"{cur} --{rel}--> {nb}" if tag == "fwd" else f"{cur} <--{rel}-- {nb}"
                parent[nb] = (cur, seg)
                depth[nb] = depth[cur] + 1
                q.append(nb)

        # 回溯链路：从每个非种子可达节点沿 parent 走回种子，再用箭头拼接
        def build_chain(node: str) -> str:
            segs: list[str] = []
            cur = node
            while cur in parent and parent[cur] is not None:
                prev, seg = parent[cur]  # type: ignore[misc]
                segs.append(seg)
                cur = prev
            segs.reverse()
            text = segs[0].split(" ", 1)[0] if segs else node  # 种子名
            for seg in segs:
                text += " " + seg.split(" ", 1)[1]  # 追加 " --关系--> 邻居"
            return text

        chains: list[str] = []
        seen_chains: set[str] = set()
        # 浅跳优先（更直接），最多取 top_chains 条
        for node in sorted(visited - seed_set, key=lambda n: depth[n]):
            ch = build_chain(node)
            if ch and ch not in seen_chains:
                seen_chains.add(ch)
                chains.append(ch)
            if len(chains) >= top_chains:
                break
        if not chains:
            chains = [f"种子实体：{s}" for s in seeds[:top_chains]]

        # 收集多跳沿途实体对应的 chunk（去重保序），拼成可注入的来源
        node_by_label = {nd["label"]: nd for nd in node_list}
        chunk_ids: list = []
        seen_cid: set = set()
        for lbl in visited:
            nd = node_by_label.get(lbl)
            if nd and nd["chunk_id"] not in seen_cid:
                chunk_ids.append(nd["chunk_id"])
                seen_cid.add(nd["chunk_id"])
        chunks: list[dict] = []
        if chunk_ids:
            rows = (
                await db.execute(
                    select(DocChunk, Document.title)
                    .join(Document, Document.id == DocChunk.document_id)
                    .where(DocChunk.id.in_(chunk_ids))
                )
            ).all()
            by_id = {c.id: (c, title) for c, title in rows}
            # 置信度按跳数衰减：种子=原始分, hop1*0.8, hop2*0.6
            decay = {0: 1.0, 1: 0.8, 2: 0.6}
            best_seed_score = max((scored[0][0],) if scored else (0.5,))
            for cid in chunk_ids:
                item = by_id.get(cid)
                if not item:
                    continue
                c, title = item
                # 找该 chunk 对应实体的深度
                conf = round(best_seed_score * 0.6, 3)  # 兆底
                for lbl in visited:
                    nd = node_by_label.get(lbl)
                    if nd and nd["chunk_id"] == cid:
                        d = depth.get(lbl, 2)
                        raw = score_by_label.get(lbl, best_seed_score) if d == 0 else best_seed_score
                        conf = round(raw * decay.get(d, 0.6), 3)
                        break
                chunks.append(
                    {
                        "chunk_id": str(c.id),
                        "kb": c.kb_id,
                        "kb_id": c.kb_id,
                        "title": title or c.kb_id,
                        "doc_id": str(c.document_id),
                        "snippet": c.content[:300],
                        "content": c.content,
                        "confidence": conf,
                        "source_type": "graph-multihop",
                    }
                )
        return chains, chunks
