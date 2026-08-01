"""ES 混合检索：kNN(向量) + BM25(关键词) + RRF 融合。

与 app.core.rag.retriever.HybridRetriever.retrieve 返回**完全同形状**的 dict 列表，
因此可在 ask.py 里无缝替换（ES 可用时优先，否则回退 HybridRetriever）。

设计：
- 向量路用 ES dense_vector 的 kNN（cosine），避免把全量 chunk 拉进内存用 numpy 算；
- 关键词路用 multi_match + ik_smart 分词做 BM25；
- 两路各取 top_k*2，再用 RRF（倒数排名融合）合成最终 top_k，
  与 HybridRetriever 思路一致，免疫两路分数量纲差异。
- ES 不可用（索引不存在 / 网络异常）时 retrieve 直接返回 []，由上层降级。
"""
from __future__ import annotations

import logging

from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.es_client import ESClient
from app.core.security import SCOPE_DEPARTMENT, SCOPE_PRIVATE, SCOPE_PUBLIC_LIKE, ScopeContext

logger = logging.getLogger("knoa.es")


class ESRetriever:
    def __init__(
        self,
        embedder: EmbeddingModel,
        es: ESClient,
        rrf_k: int = 60,
        fallback_kb_ids: "list[str] | None" = None,
        scope_ctx: ScopeContext | None = None,
    ):
        self.embedder = embedder
        self.es = es
        self.rrf_k = rrf_k
        # 「全部知识库」模式：agent 传入的 kb_id 为 None 时，跨用户可访问的
        # 全部库索引检索（缺索引的库被 ignore_unavailable 静默跳过）
        self.fallback_kb_ids = fallback_kb_ids
        # scope 补全：文档级可见性上下文（None = 不过滤）；ask.py 注入，
        # 转为 ES bool filter 下传 knn/bm25，private 文档仅上传者本人可检索。
        self._scope_ctx = scope_ctx

    def _build_scope_filter(self) -> dict | None:
        """构建 ES bool filter：仅召回当前用户可见的 chunk；admin → None（不过滤）。

        与 security.doc_scope_clause 语义一致：public 全可见，
        private 仅上传者本人，department 命中可见部门子树（visible_dept_ids）。
        """
        ctx = self._scope_ctx
        if ctx is None or ctx.is_admin:
            return None
        should = [
            {"terms": {"scope": list(SCOPE_PUBLIC_LIKE)}},
            {"bool": {"must": [
                {"term": {"scope": SCOPE_PRIVATE}},
                {"term": {"uploader_id": ctx.user_id}},
            ]}},
        ]
        if ctx.visible_dept_ids:
            should.append({"bool": {"must": [
                {"term": {"scope": SCOPE_DEPARTMENT}},
                {"terms": {"department_id": list(ctx.visible_dept_ids)}},
            ]}})
        return {
            "bool": {
                "should": should,
                "minimum_should_match": 1,
            }
        }

    async def retrieve(
        self, question: str, kb_id: str | None = None, top_k: int = 5
    ) -> list[dict]:
        # 没指定库且无回退范围 / ES 没开 → 直接空，上层会回退 pgvector
        target: "str | list[str] | None" = kb_id or self.fallback_kb_ids
        if not target or not self.es.enabled:
            return []
        # 单库快路：索引不存在直接空（上层回退）；多库不做逐库探测，
        # 由 ES ignore_unavailable 统一跳过缺失索引
        if isinstance(target, str) and not await self.es.index_exists(target):
            return []

        # 1. 向量路：query 向量化 → ES kNN（cosine）
        query_vec = await self.embedder.embed_query(question)
        # scope 补全：仅对当前用户可见的 chunk 做召回（admin 为 None 不过滤）
        scope_filter = self._build_scope_filter()
        knn_hits = await self.es.knn_search(
            target, query_vec, top_k * 2, num_candidates=max(100, top_k * 10),
            scope_filter=scope_filter,
        )

        # 2. 关键词路：ik_smart 分词后 BM25
        bm25_hits = await self.es.bm25_search(target, question, top_k * 2, scope_filter=scope_filter)

        # 3. RRF 融合（只看排名，不看原始分数）
        rrf: dict[str, float] = {}
        meta: dict[str, dict] = {}

        def add(hit: dict, rank: int, distance: float):
            cid = hit["_id"]
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (self.rrf_k + rank + 1)
            if cid not in meta:
                src = hit.get("_source", {})
                # chunk 入库时都写了 kb_id 字段；多库模式下回退用单库名
                fallback_kb = target if isinstance(target, str) else ""
                meta[cid] = {
                    "content": src.get("content", ""),
                    "kb_id": src.get("kb_id") or fallback_kb,
                    "doc_id": src.get("doc_id", ""),
                    "doc_title": src.get("doc_title", "未知文档"),
                    "distance": distance,
                }

        # 向量路：cosine 分数通常 [-1,1]，转成 0~1 区间的"距离"用于置信度展示
        for rank, hit in enumerate(knn_hits):
            score = float(hit.get("_score", 0.0))
            distance = max(0.0, 1.0 - score)
            add(hit, rank, distance)
        # 关键词路：BM25 分数量纲差异大，仅用排名；distance 置 1.0 使
        # confidence=0，前端对 0 值只显示「相关」，不会误报「100% 相关」
        for rank, hit in enumerate(bm25_hits):
            add(hit, rank, 1.0)

        sorted_ids = sorted(rrf, key=rrf.get, reverse=True)[:top_k]
        results = []
        for seq, cid in enumerate(sorted_ids, 1):
            info = meta[cid]
            confidence = max(0.0, min(1.0, 1.0 - info["distance"]))
            results.append(
                {
                    "id": seq,
                    "chunk_id": cid,
                    "content": info["content"],
                    "kb": info["kb_id"],
                    "kb_id": info["kb_id"],
                    "title": info["doc_title"],
                    "doc_id": info.get("doc_id"),
                    "doc_updated_at": None,  # ES 索引未存该字段，主检索器已补全
                    "snippet": info["content"][:150].replace("\n", " ") + "...",
                    "confidence": round(confidence, 2),
                }
            )
        return results
