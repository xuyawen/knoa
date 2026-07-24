"""Reranker：HybridRetriever 在 RRF 融合之后的精细重排层（Phase 6 §8.2）。

设计（ponytail：零硬依赖、可换模型、接口稳定）：
- 首选 cross-encoder（sentence-transformers 的 CrossEncoder）：对 (query, doc)
  对真正打分重排，效果最好。环境装不上（本环境默认）自动回退。
- 回退 "lexical-semantic"：零依赖规则重排，用
  「查询-候选 语义余弦 + BM25 归一分 + 词面重叠(Jaccard)」加权再排序。
  相比纯 RRF（只看名次、丢弃原始分数），它把语义权重调高、更贴合知识问答，
  能纠正部分 RRF 的误排。
- 暴露 before/after 顺序便于验收对比（日志）。

输入：候选 list[{cid, content, vector_score, bm25_score}]；
输出：重排（截取 top_k）后的同结构候选子集，只调顺序、不丢字段。
"""

from __future__ import annotations

import logging

import jieba


logger = logging.getLogger(__name__)

# 规则重排权重（语义为主，BM25 与词面重叠做微调）
_W_SEM = 0.62
_W_BM25 = 0.23
_W_OVERLAP = 0.15


class Reranker:
    def __init__(self, method: str = "auto", enabled: bool = True):
        self.method = (method or "auto").lower()
        self.enabled = enabled
        self._ce = None        # 懒加载的 cross-encoder
        self._ce_loaded = False

    # ---- cross-encoder 懒加载（装不上静默回退，不影响启动）----
    def _load_cross_encoder(self):
        if self._ce_loaded:
            return self._ce
        self._ce_loaded = True
        if self.method in ("auto", "cross-encoder"):
            try:
                from sentence_transformers import CrossEncoder

                self._ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                logger.info("reranker: cross-encoder loaded")
            except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort, fallback to lexical-semantic reranker if cross-encoder unavailable)
                logger.info("reranker: cross-encoder unavailable (%s), fallback lexical-semantic", e)
                self._ce = None
        return self._ce

    def rerank(self, question: str, candidates: list[dict], top_k: int) -> list[dict]:
        """对 RRF 候选做精细重排，返回顺序调整后的子集（最多 top_k 条）。"""
        if not candidates:
            return []
        if not self.enabled:
            return list(candidates)[:top_k]

        ce = self._load_cross_encoder()
        if ce is not None:
            try:
                pairs = [(question, c.get("content", "")) for c in candidates]
                scores = [float(s) for s in ce.predict(pairs)]
                ranked = sorted(zip(candidates, scores, strict=True), key=lambda x: x[1], reverse=True)
                return [c for c, _ in ranked][:top_k]
            except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort, fallback to lexical-semantic if cross-encoder predict fails)
                logger.warning("reranker: cross-encoder predict failed (%s), fallback", e)

        # ---- 回退：lexical-semantic 规则重排 ----
        q_tokens = set(jieba.cut_for_search(question))
        max_bm25 = max((float(c.get("bm25_score", 0.0)) for c in candidates), default=1.0) or 1.0
        scored = []
        for c in candidates:
            content = c.get("content", "") or ""
            sem = max(0.0, float(c.get("vector_score", 0.0)))  # 余弦 [-1,1] → [0,1]
            norm_bm25 = float(c.get("bm25_score", 0.0)) / max_bm25
            c_tokens = set(jieba.cut_for_search(content))
            union = q_tokens | c_tokens
            overlap = (len(q_tokens & c_tokens) / len(union)) if union else 0.0
            final = _W_SEM * sem + _W_BM25 * norm_bm25 + _W_OVERLAP * overlap
            scored.append((c, final))
        ranked = sorted(scored, key=lambda x: x[1], reverse=True)
        return [c for c, _ in ranked][:top_k]
