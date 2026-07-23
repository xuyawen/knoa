import time

import logging

import jieba
import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.reranker import Reranker
from app.db import DocChunk, Document, KnowledgeBase

logger = logging.getLogger(__name__)

try:
    from langsmith import traceable
except ImportError:
    def traceable(**kwargs):
        def decorator(fn):
            return fn
        return decorator


# BM25 / 召回索引缓存：按 KB 范围缓存已 tokenize 的 BM25 对象 + 过滤后的
# chunk 列表（纯 dict），避免每个请求都全表 load + 重新 jieba 分词（jieba
# cut_for_search 在大语料上很慢）。写侧（摄入 / 删除）变更后靠 TTL（60s）
# 自然失效，简单且不会跨请求持有已过期的 ORM 对象。
_BM25_CACHE: dict[str, dict] = {}
_BM25_TTL = 60  # 秒


def _cache_key(kb_id: str | None, kb_ids_filter: list[str] | None) -> str:
    if kb_id:
        return f"kb:{kb_id}"
    if kb_ids_filter:
        return "filt:" + ",".join(sorted(kb_ids_filter))
    return "all"


def _chunk_to_dict(c) -> dict:
    """把 ORM DocChunk 转成纯 dict，便于跨请求缓存（避免复用不同会话的 ORM 对象）。"""
    return {
        "id": c.id,
        "embedding": c.embedding,
        "content": c.content,
        "kb_id": c.kb_id,
        "document_id": c.document_id,
    }


class HybridRetriever:
    """向量检索(numpy 余弦) + BM25 检索 + RRF 融合"""

    def __init__(
        self,
        embedder: EmbeddingModel,
        db: AsyncSession,
        rrf_k: int = 60,
        kb_ids: "list[str] | None" = None,
    ):
        self.embedder = embedder
        self.db = db
        self.rrf_k = rrf_k
        # 实例级可访问 KB 范围（None = 不限，仅 admin/显式单库时使用）。
        # 仅当每次检索未传入具体 kb_id 时生效，用于「未指定 KB 时」
        # 把检索严格限定在该用户有权访问的 KB 集合内，防止跨库越权。
        self._kb_ids_filter = kb_ids
        self._bm25: BM25Okapi | None = None
        self._bm25_chunks: list = []
        # 8.2 Reranker：RRF 之后的精细重排层（零依赖规则，可换 cross-encoder）
        self.reranker = Reranker(settings.RERANKER_METHOD, settings.RERANKER_ENABLED)

    async def _load_chunks(self, kb_id: str | None = None):
        query = select(DocChunk)
        if kb_id:
            query = query.where(DocChunk.kb_id == kb_id)
        elif self._kb_ids_filter:
            query = query.where(DocChunk.kb_id.in_(self._kb_ids_filter))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    @traceable(name="retrieve", tags=["retrieval"])
    async def retrieve(self, question: str, kb_id: str | None = None, top_k: int = 5) -> list[dict]:
        query_vec = np.array(await self.embedder.embed_query(question))

        key = _cache_key(kb_id, self._kb_ids_filter)
        now = time.monotonic()
        entry = _BM25_CACHE.get(key)
        if entry and now - entry["ts"] < _BM25_TTL:
            # 命中缓存：复用已分词好的 BM25 与过滤后的 chunk 列表
            chunks = entry["chunks"]
            self._bm25 = entry["bm25"]
            self._bm25_chunks = chunks
        else:
            raw = await self._load_chunks(kb_id)
            if not raw:
                return []
            # 过滤维度不符/为空的脏 chunk（库里存在 8 维脏数据，会让
            # chunk_embeddings @ query_vec 维度不匹配 -> 500）。chunks 同步
            # 过滤以保持与 cosine_scores 的索引对齐（后续用索引回查 chunks）。
            valid = [
                _chunk_to_dict(c) for c in raw
                if c.embedding is not None and len(c.embedding) == query_vec.shape[0]
            ]
            if not valid:
                return []
            chunks = valid
            # 构建 BM25（jieba 分词是大头，靠缓存避免每请求重算）
            tokenized = [list(jieba.cut_for_search(c["content"])) for c in chunks]
            self._bm25 = BM25Okapi(tokenized)
            self._bm25_chunks = chunks
            _BM25_CACHE[key] = {"ts": now, "chunks": chunks, "bm25": self._bm25}

        # 1. 向量检索 (numpy 余弦相似度, 归一化向量直接点积)
        chunk_embeddings = np.array([c["embedding"] for c in chunks])
        cosine_scores = chunk_embeddings @ query_vec  # 归一化向量点积 = 余弦
        vector_ranked = sorted(
            enumerate(cosine_scores), key=lambda x: x[1], reverse=True
        )[: top_k * 2]

        # 2. BM25 检索
        tokens = list(jieba.cut_for_search(question))
        bm25_scores = self._bm25.get_scores(tokens)
        bm25_ranked = sorted(enumerate(bm25_scores), key=lambda x: x[1], reverse=True)[
            : top_k * 2
        ]

        # 3. 预取 KB 名称和文档标题
        kb_names = await self._batch_get_kb_names()
        doc_ids = {str(c["document_id"]) for c in chunks}
        doc_titles = await self._batch_get_doc_titles(list(doc_ids))

        # 4. RRF 融合
        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, dict] = {}

        def add_chunk(idx, rank, distance):
            chunk = chunks[idx]
            cid = str(chunk["id"])
            rrf_scores[cid] = rrf_scores.get(cid, 0) + 1.0 / (self.rrf_k + rank + 1)
            if cid not in chunk_map:
                chunk_map[cid] = {
                    "content": chunk["content"],
                    "kb_id": chunk["kb_id"],
                    "kb_name": kb_names.get(chunk["kb_id"], chunk["kb_id"]),
                    "doc_title": doc_titles.get(str(chunk["document_id"]), "未知文档"),
                    "distance": distance,
                }

        for rank, (idx, score) in enumerate(vector_ranked):
            add_chunk(idx, rank, 1.0 - float(score))
        for rank, (idx, score) in enumerate(bm25_ranked):
            if idx < len(chunks):
                add_chunk(idx, rank, 0.0)

        # 排序取 top_k（RRF 原始顺序，留作重排对比基线）
        pre_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]

        # 8.2 Reranker：用原始语义/BM25 分数做精细重排（接口不变，只调顺序）
        idx_by_cid = {str(chunks[i]["id"]): i for i in range(len(chunks))}
        candidates = []
        for cid in pre_ids:
            i = idx_by_cid.get(cid)
            if i is None:
                continue
            candidates.append({
                "cid": cid,
                "content": chunk_map[cid]["content"],
                "vector_score": float(cosine_scores[i]),
                "bm25_score": float(bm25_scores[i]),
            })
        reranked = self.reranker.rerank(question, candidates, top_k)
        reranked_ids = [c["cid"] for c in reranked]
        if self.reranker.enabled:
            logger.info("rerank order change: before=%s after=%s", pre_ids, reranked_ids)

        results = []
        for seq, cid in enumerate(reranked_ids, 1):
            info = chunk_map[cid]
            confidence = max(0.0, min(1.0, 1.0 - info["distance"]))
            results.append({
                "id": seq,
                "chunk_id": cid,
                "content": info["content"],
                "kb": info["kb_name"],
                "kb_id": info["kb_id"],
                "title": info["doc_title"],
                "doc_id": info["document_id"],
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
