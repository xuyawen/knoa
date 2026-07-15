import jieba
import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rag.embeddings import EmbeddingModel
from app.db import DocChunk, Document, KnowledgeBase

try:
    from langsmith import traceable
except ImportError:
    def traceable(**kwargs):
        def decorator(fn):
            return fn
        return decorator


class HybridRetriever:
    """向量检索(numpy 余弦) + BM25 检索 + RRF 融合"""

    def __init__(self, embedder: EmbeddingModel, db: AsyncSession, rrf_k: int = 60):
        self.embedder = embedder
        self.db = db
        self.rrf_k = rrf_k
        self._bm25: BM25Okapi | None = None
        self._bm25_chunks: list = []

    async def _load_chunks(self, kb_id: str | None = None):
        query = select(DocChunk)
        if kb_id:
            query = query.where(DocChunk.kb_id == kb_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    @traceable(name="retrieve", tags=["retrieval"])
    async def retrieve(self, question: str, kb_id: str | None = None, top_k: int = 5) -> list[dict]:
        chunks = await self._load_chunks(kb_id)
        if not chunks:
            return []

        # 1. 向量检索 (numpy 余弦相似度, 归一化向量直接点积)
        query_vec = np.array(await self.embedder.embed_query(question))
        # 过滤维度不符/为空的脏 chunk（库里存在 8 维脏数据，会让
        # chunk_embeddings @ query_vec 维度不匹配 -> 500）。chunks 同步
        # 过滤以保持与 cosine_scores 的索引对齐（后续用索引回查 chunks）。
        valid = [
            c for c in chunks
            if c.embedding is not None and len(c.embedding) == query_vec.shape[0]
        ]
        if not valid:
            return []
        chunks = valid
        chunk_embeddings = np.array([c.embedding for c in chunks])
        cosine_scores = chunk_embeddings @ query_vec  # 归一化向量点积 = 余弦
        vector_ranked = sorted(
            enumerate(cosine_scores), key=lambda x: x[1], reverse=True
        )[: top_k * 2]

        # 2. BM25 检索
        if self._bm25 is None or len(chunks) != len(self._bm25_chunks):
            self._bm25_chunks = chunks
            tokenized = [list(jieba.cut_for_search(c.content)) for c in chunks]
            self._bm25 = BM25Okapi(tokenized)

        tokens = list(jieba.cut_for_search(question))
        bm25_scores = self._bm25.get_scores(tokens)
        bm25_ranked = sorted(enumerate(bm25_scores), key=lambda x: x[1], reverse=True)[
            : top_k * 2
        ]

        # 3. 预取 KB 名称和文档标题
        kb_names = await self._batch_get_kb_names()
        doc_ids = {str(c.document_id) for c in chunks}
        doc_titles = await self._batch_get_doc_titles(list(doc_ids))

        # 4. RRF 融合
        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, dict] = {}

        def add_chunk(idx, rank, distance):
            chunk = chunks[idx]
            cid = str(chunk.id)
            rrf_scores[cid] = rrf_scores.get(cid, 0) + 1.0 / (self.rrf_k + rank + 1)
            if cid not in chunk_map:
                chunk_map[cid] = {
                    "content": chunk.content,
                    "kb_id": chunk.kb_id,
                    "kb_name": kb_names.get(chunk.kb_id, chunk.kb_id),
                    "doc_title": doc_titles.get(str(chunk.document_id), "未知文档"),
                    "distance": distance,
                }

        for rank, (idx, score) in enumerate(vector_ranked):
            add_chunk(idx, rank, 1.0 - float(score))
        for rank, (idx, score) in enumerate(bm25_ranked):
            if idx < len(chunks):
                add_chunk(idx, rank, 0.0)

        # 排序取 top_k
        sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]
        results = []
        for seq, cid in enumerate(sorted_ids, 1):
            info = chunk_map[cid]
            confidence = max(0.0, min(1.0, 1.0 - info["distance"]))
            results.append({
                "id": seq,
                "chunk_id": cid,
                "content": info["content"],
                "kb": info["kb_name"],
                "title": info["doc_title"],
                "snippet": info["content"][:150].replace("\n", " ") + "...",
                "confidence": round(confidence, 2),
            })
        return results

    async def _batch_get_kb_names(self) -> dict[str, str]:
        result = await self.db.execute(select(KnowledgeBase.id, KnowledgeBase.name))
        return {row.id: row.name for row in result}

    async def _batch_get_doc_titles(self, doc_ids: list[str]) -> dict[str, str]:
        if not doc_ids:
            return {}
        result = await self.db.execute(
            select(Document.id, Document.title).where(Document.id.in_(doc_ids))
        )
        return {str(row.id): row.title for row in result}
