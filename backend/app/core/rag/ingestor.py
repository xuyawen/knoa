import logging
from pathlib import Path

import asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rag.chunker import MarkdownChunker
from app.core.rag.embeddings import EmbeddingModel
from app.core.graph import GraphStore
from app.core.rag.es_client import ESClient
from app.database import AsyncSessionLocal
from app.db import DocChunk, Document

logger = logging.getLogger(__name__)

# 后台图谱抽取任务引用集：持有 task 到完成，防止被 CPython GC 取消
# （与 routers/knowledge.py 的 _spawn_background 同款机制）
_BACKGROUND_TASKS: set = set()


def _spawn_graph_task(coro):
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


class DocumentIngester:
    def __init__(
        self,
        embedder: EmbeddingModel,
        chunk_size: int = 500,
        overlap: int = 50,
        min_chunk_chars: int = 10,
        es: ESClient | None = None,
        graph: GraphStore | None = None,
        background_graph: bool = True,
    ):
        self.embedder = embedder
        self.chunker = MarkdownChunker(chunk_size, overlap, min_chunk_chars)
        # ES 客户端（可选）：传入则摄入时双写到 ES 索引，否则只写 pgvector
        self._es = es
        # 知识图谱（可选）：传入则摄入时抽取实体/关系写入图（Phase 3 T1）
        self._graph = graph
        # 8.4 KG 回填：建图抽取是否后台独立会话执行。
        # True（API 审核/上传路径）= 不阻塞主响应、失败隔离；
        # False（seed 全量重建，跑在 asyncio.run 内）= 内联同步，确保进程退出前完成。
        self.background_graph = background_graph

    async def _maybe_graph_extract(self, kb_id: str, doc: Document, db: AsyncSession) -> None:
        """建图抽取：后台（独立会话，不阻塞主流程、失败隔离）或内联（seed 重建）。"""
        if self._graph is None:
            return
        if self.background_graph:
            self._schedule_graph_extract(kb_id, doc.id)
        else:
            chunk_infos = await self._chunk_infos(db, doc.id)
            if chunk_infos:
                await self._graph.extract(kb_id, doc.title, chunk_infos, db)

    def _schedule_graph_extract(self, kb_id: str, doc_id: object) -> None:
        """后台异步抽取图谱：用独立 DB 会话，无运行事件环则跳过（不阻塞）。
        任务引用由 _spawn_graph_task 持有，避免被事件循环 GC 提前取消。"""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("graph extract skipped (no running loop) for doc %s", doc_id)
            return
        _spawn_graph_task(self._background_graph_extract(kb_id, doc_id))

    async def _background_graph_extract(self, kb_id: str, doc_id: object) -> None:
        """独立会话重抽图谱：重新拉 chunk → LLM 抽取 → 独立提交；失败不影响主流程。"""
        try:
            async with AsyncSessionLocal() as s:
                doc = await s.get(Document, doc_id)
                if doc is None:
                    return
                chunk_infos = await self._chunk_infos(s, doc_id)
                if not chunk_infos:
                    return
                await self._graph.extract(kb_id, doc.title, chunk_infos, s)
                await s.commit()
        except Exception as e:
            logger.warning("background graph extract failed (kb=%s doc=%s): %s", kb_id, doc_id, e)

    async def ingest_dir(self, kb_id: str, dir_path: Path, db: AsyncSession):
        md_files = sorted(dir_path.glob("*.md"))
        # 双写：确保该 KB 的 ES 索引存在（幂等；不可用时返回 False，静默跳过）
        if self._es is not None:
            await self._es.ensure_index(kb_id)
        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")
            title = self._extract_title(content, md_file.stem)

            doc = Document(
                kb_id=kb_id,
                title=title,
                source_path=str(md_file),
                content_md=content,
                status="已审核",  # 开发者灌库的内容视为已审核/可检索
            )
            db.add(doc)
            await db.flush()

            chunks = self.chunker.chunk(content, title)
            texts = [c["content"] for c in chunks]
            if not texts:
                continue
            embeddings = await self.embedder.embed(texts)

            for chunk_data, embedding in zip(chunks, embeddings, strict=True):
                db.add(
                    DocChunk(
                        document_id=doc.id,
                        kb_id=kb_id,
                        chunk_index=chunk_data["index"],
                        content=chunk_data["content"],
                        embedding=embedding,
                    )
                )
                # 双写 ES（幂等：用确定性 _id，失败静默不影响主流程）
                await self._sync_es_chunk(kb_id, doc, chunk_data, embedding)
            await db.flush()

            # 建图：把这篇文档的 chunk 交给 GraphStore 抽取实体/关系
            # （失败静默跳过；后台或内联由 background_graph 决定）
            if self._graph is not None:
                await self._maybe_graph_extract(kb_id, doc, db)
        await db.commit()

    async def _sync_es_chunk(
        self, kb_id: str, doc: Document, chunk_data: dict, embedding: list
    ) -> None:
        """把一个 chunk 同步进 ES 索引（摄入双写）。ES 不可用时静默跳过。"""
        if self._es is None or not self._es.enabled:
            return
        # 确定性 _id：kb_id + doc.id + chunk_index，保证重复摄入幂等覆盖
        es_id = f"{kb_id}_{doc.id}_{chunk_data['index']}"
        body = {
            "content": chunk_data["content"],
            "embedding": embedding,
            "kb_id": kb_id,
            "doc_id": str(doc.id),
            "chunk_index": chunk_data["index"],
            "doc_title": doc.title,
        }
        await self._es.upsert_chunk(kb_id, es_id, body)


    async def ingest_existing(self, doc: Document, db: AsyncSession) -> None:
        """对已落库（含 content_md）的 Document 执行摄入：切分 + 向量化 + 写 DocChunk + ES + 图谱。

        方案 A（延迟摄入）核心：上传时只建 Document(status=待复核) 不摄入，
        审核通过后再调本方法把这篇文档真正切分进检索库。
        与 ingest_dir 共享同一套 chunk/embed/ES/图谱逻辑，保证行为一致。
        """
        # 幂等摄入：先清该文档旧 chunk（PG）+ ES + 图谱，
        # 避免「审核通过 → 驳回 → 再审核通过」路径产生重复向量块 / 脏图节点
        # 注意：清图谱节点需按 chunk_id 定位（KGNode.chunk_id 指向 DocChunk.id），
        # 必须在删除 DocChunk 之前先把旧 chunk id 收集出来，否则删完就查不到了。
        old_chunk_ids = (
            await db.execute(
                select(DocChunk.id).where(DocChunk.document_id == doc.id)
            )
        ).scalars().all()
        await db.execute(delete(DocChunk).where(DocChunk.document_id == doc.id))
        if self._es is not None and self._es.enabled:
            await self._es.delete_by_doc(doc.kb_id, doc.id)
        if self._graph is not None:
            await self._graph.delete_by_doc(db, doc.kb_id, list(old_chunk_ids))

        # 双写：确保该 KB 的 ES 索引存在（幂等；不可用时返回 False，静默跳过）。
        if self._es is not None:
            await self._es.ensure_index(doc.kb_id)
        chunks = self.chunker.chunk(doc.content_md, doc.title)
        texts = [c["content"] for c in chunks]
        if texts:
            embeddings = await self.embedder.embed(texts)
            for chunk_data, embedding in zip(chunks, embeddings, strict=True):
                db.add(
                    DocChunk(
                        document_id=doc.id,
                        kb_id=doc.kb_id,
                        chunk_index=chunk_data["index"],
                        content=chunk_data["content"],
                        embedding=embedding,
                    )
                )
                await self._sync_es_chunk(doc.kb_id, doc, chunk_data, embedding)
            await db.flush()

            # 建图：抽实体进图谱（与 ingest_dir 一致；后台或内联由 background_graph 决定）
            if self._graph is not None:
                await self._maybe_graph_extract(doc.kb_id, doc, db)
        await db.commit()

    async def ingest_text(
        self,
        kb_id: str,
        title: str,
        content: str,
        db: AsyncSession,
        source_path: str = "upload",
    ) -> Document:
        """单篇文本摄入：建 Document + 切分 + 向量化 + 写 DocChunk。"""
        doc = Document(
            kb_id=kb_id,
            title=title,
            source_path=source_path,
            content_md=content,
            status="待复核",  # 用户上传文档待人工复核后再纳入正式知识
        )
        db.add(doc)
        await db.flush()
        # 复用 ingest_existing，保证 seed 与审核摄入走同一套逻辑
        await self.ingest_existing(doc, db)
        return doc

    async def _chunk_infos(self, db: AsyncSession, doc_id: object) -> list[dict]:
        """从 DB 取某文档的全部 chunk（按 chunk_index 排序），拼成图抽取要的结构。

        GraphStore.extract 需要每个 chunk 的 content + 真实 chunk_id（建表后才生成），
        所以得在 DocChunk 入库 flush 之后从 DB 查回来，而不是用 chunker 的原始输出。
        """
        rows = (
            await db.execute(
                select(DocChunk)
                .where(DocChunk.document_id == doc_id)
                .order_by(DocChunk.chunk_index)
            )
        ).scalars().all()
        return [
            {"index": c.chunk_index, "content": c.content, "chunk_id": c.id}
            for c in rows
        ]

    def _extract_title(self, content: str, fallback: str) -> str:
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return fallback
