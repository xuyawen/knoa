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

logger = logging.getLogger("knoa.es")


class ESRetriever:
    def __init__(self, embedder: EmbeddingModel, es: ESClient, rrf_k: int = 60):
        self.embedder = embedder
        self.es = es
        self.rrf_k = rrf_k

    async def retrieve(
        self, question: str, kb_id: str | None = None, top_k: int = 5
    ) -> list[dict]:
        # 没指定库 / ES 没开 / 该库索引还不存在 → 直接空，上层会回退 pgvector
        if not kb_id or not self.es.enabled:
            return []
        if not await self.es.index_exists(kb_id):
            return []

        # 1. 向量路：query 向量化 → ES kNN（cosine）
        query_vec = await self.embedder.embed_query(question)
        knn_hits = await self.es.knn_search(
            kb_id, query_vec, top_k * 2, num_candidates=max(100, top_k * 10)
        )

        # 2. 关键词路：ik_smart 分词后 BM25
        bm25_hits = await self.es.bm25_search(kb_id, question, top_k * 2)

        # 3. RRF 融合（只看排名，不看原始分数）
        rrf: dict[str, float] = {}
        meta: dict[str, dict] = {}

        def add(hit: dict, rank: int, distance: float):
            cid = hit["_id"]
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (self.rrf_k + rank + 1)
            if cid not in meta:
                src = hit.get("_source", {})
                meta[cid] = {
                    "content": src.get("content", ""),
                    "kb_id": src.get("kb_id", kb_id),
                    "doc_title": src.get("doc_title", "未知文档"),
                    "distance": distance,
                }

        # 向量路：cosine 分数通常 [-1,1]，转成 0~1 区间的"距离"用于置信度展示
        for rank, hit in enumerate(knn_hits):
            score = float(hit.get("_score", 0.0))
            distance = max(0.0, 1.0 - score)
            add(hit, rank, distance)
        # 关键词路：BM25 分数量纲差异大，仅用排名，distance 置 0
        for rank, hit in enumerate(bm25_hits):
            add(hit, rank, 0.0)

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
                    "title": info["doc_title"],
                    "snippet": info["content"][:150].replace("\n", " ") + "...",
                    "confidence": round(confidence, 2),
                }
            )
        return results
