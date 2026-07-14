from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rag.chunker import MarkdownChunker
from app.core.rag.embeddings import EmbeddingModel
from app.core.graph import GraphStore
from app.core.rag.es_client import ESClient
from app.db import DocChunk, Document


class DocumentIngester:
    def __init__(
        self,
        embedder: EmbeddingModel,
        chunk_size: int = 500,
        overlap: int = 50,
        es: ESClient | None = None,
        graph: GraphStore | None = None,
    ):
        self.embedder = embedder
        self.chunker = MarkdownChunker(chunk_size, overlap)
        # ES 客户端（可选）：传入则摄入时双写到 ES 索引，否则只写 pgvector
        self._es = es
        # 知识图谱（可选）：传入则摄入时抽取实体/关系写入图（Phase 3 T1）
        self._graph = graph

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

            # 建图：把这篇文档的 chunk 交给 GraphStore 抽取实体/关系（失败静默跳过）
            if self._graph is not None:
                chunk_infos = await self._chunk_infos(db, doc.id)
                await self._graph.extract(kb_id, doc.title, chunk_infos, db)
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

            # 建图：抽实体进图谱（与 ingest_dir 一致）
            if self._graph is not None:
                chunk_infos = await self._chunk_infos(db, doc.id)
                await self._graph.extract(doc.kb_id, doc.title, chunk_infos, db)
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
