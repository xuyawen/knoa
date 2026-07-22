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
from app.db import KnowledgeBase

KB_DIRS = ["compliance", "ads", "logistics", "selection", "service"]

# 每个 seed 域的展示元信息（id 与目录名一致, icon 与前端 Icon.vue 对齐）
KB_META = {
    "compliance": {"name": "合规政策", "icon": "compliance", "description": "亚马逊账户健康、封号申诉、知识产权保护等合规指南"},
    "ads":        {"name": "广告运营", "icon": "ads",        "description": "亚马逊 PPC / SB / SD 广告策略与投放技巧"},
    "logistics":  {"name": "物流仓储", "icon": "logistics",  "description": "FBA 头程、海外仓、包装与运输方案"},
    "selection":  {"name": "选品策略", "icon": "selection",  "description": "市场调研、竞品分析、蓝海选品方法论"},
    "service":    {"name": "客户服务", "icon": "service",    "description": "售后处理、退换货、Review 管理与客服话术"},
}


async def main():
    await init_db()
    embedder = EmbeddingModel(settings.EMBEDDING_MODEL)
    # 知识图谱（Phase 3 T1）：seed 同时建图
    graph = GraphStore(get_llm(), embedder)
    # 双写：若 ES_ENABLED=True 则摄入同时写入 ES 索引（幂等覆盖）
    ingester = DocumentIngester(
        embedder, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP,
        settings.RAG_CHUNK_MIN_CHARS, es=ESClient(), graph=graph,
        background_graph=False,  # seed 跑在 asyncio.run 内，必须内联同步完成
    )

    async with AsyncSessionLocal() as db:
        # 清空旧数据 (幂等)
        await db.execute(text("DELETE FROM doc_chunk"))
        await db.execute(text("DELETE FROM document"))
        # 清空旧图谱：seed 是「重建全集」路径，避免实体/边重复堆积与孤儿节点
        await db.execute(text("DELETE FROM kg_edge"))
        await db.execute(text("DELETE FROM kg_node"))
        # 清空旧的 KB 记录（seed 是全量重建）
        await db.execute(text("DELETE FROM kb_permission"))
        await db.execute(text("DELETE FROM knowledge_base"))
        await db.commit()

        # 创建 5 个知识库记录（FK 前置：document.kb_id 引用 knowledge_base.id）
        for kb_id, meta in KB_META.items():
            kb = KnowledgeBase(
                id=kb_id,
                name=meta["name"],
                icon=meta["icon"],
                description=meta["description"],
            )
            db.add(kb)
        await db.commit()
        print(f"Created {len(KB_META)} knowledge bases.")

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
