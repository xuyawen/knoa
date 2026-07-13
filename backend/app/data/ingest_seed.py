"""扫描 app/data/markdown/ 下所有域, 执行文档摄入。可执行: python -m app.data.ingest_seed"""
import asyncio
from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.es_client import ESClient
from app.core.rag.ingestor import DocumentIngester
from app.database import AsyncSessionLocal, init_db
from app.core.graph import GraphStore
from app.deps import get_llm

KB_DIRS = ["compliance", "ads", "logistics", "selection", "service"]


async def main():
    await init_db()
    embedder = EmbeddingModel(settings.EMBEDDING_MODEL)
    # 知识图谱（Phase 3 T1）：seed 同时建图
    graph = GraphStore(get_llm(), embedder)
    # 双写：若 ES_ENABLED=True 则摄入同时写入 ES 索引（幂等覆盖）
    ingester = DocumentIngester(
        embedder, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP, es=ESClient(), graph=graph
    )

    async with AsyncSessionLocal() as db:
        # 清空旧数据 (幂等)
        await db.execute(text("DELETE FROM doc_chunk"))
        await db.execute(text("DELETE FROM document"))
        # 清空旧图谱：seed 是「重建全集」路径，避免实体/边重复堆积与孤儿节点
        await db.execute(text("DELETE FROM kg_edge"))
        await db.execute(text("DELETE FROM kg_node"))
        await db.commit()

        base = Path(__file__).parent / "markdown"
        total = 0
        for kb_id in KB_DIRS:
            dir_path = base / kb_id
            if dir_path.exists():
                count = len(list(dir_path.glob("*.md")))
                print(f"Ingesting {kb_id} ({count} files)...")
                await ingester.ingest_dir(kb_id, dir_path, db)
                total += count
                print(f"  done.")

    print(f"All done: {total} documents ingested.")


if __name__ == "__main__":
    asyncio.run(main())
