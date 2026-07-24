"""Elasticsearch 客户端封装（Phase 2 混合检索）。

约束与设计原则：
- venv 装不了 elasticsearch 官方客户端，因此直接走 httpx 异步 REST（与 web_search 同一套路）。
- ES 是**可选组件**：ES_ENABLED=False、或 URL 未配置、或任何网络/解析异常，
  所有方法一律优雅降级（返回 None / [] / 空操作），**绝不**因 ES 问题导致
  主链路（问答 / 摄入）崩溃。上端（ask.py / ingestor）在 ES 不可用时自动回退 pgvector。
- 每知识库一个索引，命名 {prefix}_{kb_id}（如 kb_kb_abc123）。
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("knoa.es")


class ESClient:
    def __init__(self):
        # 总开关：显式开启且配置了 URL 才算启用
        self.enabled = bool(settings.ES_ENABLED and settings.ES_URL)
        self.base = settings.ES_URL.rstrip("/")
        self.index_prefix = settings.ES_INDEX_PREFIX
        self.timeout = settings.ES_REQUEST_TIMEOUT
        self._client: httpx.AsyncClient | None = None
        self._auth = None
        if settings.ES_USERNAME:
            self._auth = (settings.ES_USERNAME, settings.ES_PASSWORD)

    # ------------------------------------------------------------------ #
    # 底层 REST 封装
    # ------------------------------------------------------------------ #
    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base,
                auth=self._auth,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def aclose(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(
        self, method: str, path: str, *, json_body: Any = None
    ) -> dict | None:
        """发一次 REST 请求，统一吞掉所有异常。

        返回 dict（成功，可能为 {}）或 None（ES 未启用 / 失败 / HTTP>=400）。
        ES 用 HTTP 状态码表达错误（404 索引不存在、409 冲突等），这里不抛，
        交由调用方按 None 降级。
        """
        if not self.enabled:
            return None
        try:
            resp = await self._get_client().request(
                method,
                path,
                content=json.dumps(json_body) if json_body is not None else None,
            )
            if resp.status_code >= 400:
                logger.warning(
                    "[es] %s %s -> HTTP %s: %s",
                    method, path, resp.status_code, resp.text[:200],
                )
                return None
            return resp.json() if resp.content else {}
        except Exception as e:  # noqa: BLE001  (intentional catch-all: ES is optional, swallow all errors to degrade gracefully to None)
            logger.warning("[es] %s %s request failed: %s", method, path, e)
            return None

    # ------------------------------------------------------------------ #
    # 索引管理（每知识库一个索引）
    # ------------------------------------------------------------------ #
    def index_name(self, kb_id: str) -> str:
        return f"{self.index_prefix}_{kb_id}"

    async def index_exists(self, kb_id: str) -> bool:
        if not self.enabled:
            return False
        # HEAD 成功（200）时 _request 返回 {}，失败（404）返回 None
        return await self._request("HEAD", f"/{self.index_name(kb_id)}") is not None

    async def ensure_index(self, kb_id: str) -> bool:
        """创建索引（幂等）。已存在则跳过。返回该索引是否可用。"""
        if not self.enabled:
            return False
        name = self.index_name(kb_id)
        if await self.index_exists(kb_id):
            return True
        # content: IK 分词（入库细粒度 ik_max_word，检索高效 ik_smart）
        # embedding: dense_vector，余弦相似度，供 kNN 向量检索
        mapping = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
            "mappings": {
                "properties": {
                    "content": {
                        "type": "text",
                        "analyzer": "ik_max_word",
                        "search_analyzer": "ik_smart",
                    },
                    "embedding": {
                        "type": "dense_vector",
                        "dims": settings.EMBEDDING_DIM,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "kb_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "doc_title": {"type": "keyword"},
                }
            },
        }
        return await self._request("PUT", f"/{name}", json_body=mapping) is not None

    async def delete_index(self, kb_id: str) -> None:
        """删除整个知识库索引（未来接 KB 删除端点时调用）。"""
        if not self.enabled:
            return
        await self._request("DELETE", f"/{self.index_name(kb_id)}")

    # ------------------------------------------------------------------ #
    # 文档（chunk）读写
    # ------------------------------------------------------------------ #
    async def upsert_chunk(self, kb_id: str, chunk_id: str, body: dict) -> None:
        """写入 / 覆盖一个 chunk。用确定性的 chunk_id 作 _id，重复摄入幂等。"""
        if not self.enabled:
            return
        name = self.index_name(kb_id)
        # op_type=index 即覆盖写，保证重摄入不重复
        await self._request("PUT", f"/{name}/_doc/{chunk_id}", json_body=body)

    async def delete_by_doc(self, kb_id: str, doc_id: str) -> None:
        """删除某个文档下的全部 chunk（删除文档时清理）。"""
        if not self.enabled:
            return
        name = self.index_name(kb_id)
        query = {"query": {"term": {"doc_id": str(doc_id)}}}
        await self._request("POST", f"/{name}/_delete_by_query", json_body=query)

    # ------------------------------------------------------------------ #
    # 检索（两路，分别返回 ES hits，由 es_retriever 做 RRF 融合）
    # ------------------------------------------------------------------ #
    async def knn_search(
        self, kb_id: str, query_vector: list[float], size: int, num_candidates: int = 100
    ) -> list[dict]:
        """向量路：kNN 余弦检索。"""
        if not self.enabled:
            return []
        name = self.index_name(kb_id)
        body = {
            "size": size,
            "knn": {
                "field": "embedding",
                "query_vector": query_vector,
                "k": size,
                "num_candidates": num_candidates,
            },
        }
        r = await self._request("POST", f"/{name}/_search", json_body=body)
        if not r or "hits" not in r:
            return []
        return r["hits"]["hits"]

    async def bm25_search(self, kb_id: str, query: str, size: int) -> list[dict]:
        """关键词路：multi_match + ik_smart 分词（BM25 打分）。"""
        if not self.enabled:
            return []
        name = self.index_name(kb_id)
        body = {
            "size": size,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["content"],
                    "analyzer": "ik_smart",
                }
            },
        }
        r = await self._request("POST", f"/{name}/_search", json_body=body)
        if not r or "hits" not in r:
            return []
        return r["hits"]["hits"]
