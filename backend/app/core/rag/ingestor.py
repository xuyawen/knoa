from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rag.chunker import MarkdownChunker
from app.core.rag.embeddings import EmbeddingModel
from app.db import DocChunk, Document


class DocumentIngester:
    def __init__(self, embedder: EmbeddingModel, chunk_size: int = 500, overlap: int = 50):
        self.embedder = embedder
        self.chunker = MarkdownChunker(chunk_size, overlap)

    async def ingest_dir(self, kb_id: str, dir_path: Path, db: AsyncSession):
        md_files = sorted(dir_path.glob("*.md"))
        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")
            title = self._extract_title(content, md_file.stem)

            doc = Document(
                kb_id=kb_id,
                title=title,
                source_path=str(md_file),
                content_md=content,
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
            await db.flush()
        await db.commit()

    def _extract_title(self, content: str, fallback: str) -> str:
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return fallback
