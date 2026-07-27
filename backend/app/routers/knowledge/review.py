"""文档审核流路由：通过（触发摄入）/ 驳回 / AI 辅助审核 + 后台摄入任务。"""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.graph import GraphStore
from app.core.llm.openai_compat import OpenAICompatProvider
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.ingestor import DocumentIngester
from app.core.security import require_kb_access
from app.database import AsyncSessionLocal
from app.db import Document, DocumentTask, User
from app.deps import get_db, get_embedder, get_es, get_llm
from app.models.knowledge import AIReviewOut, DocumentOut
from app.models.operation_log import record_operation
from app.routers.knowledge.common import doc_out

logger = logging.getLogger(__name__)

router = APIRouter()

# 后台任务引用集：与 agent.py 同款机制，持有 task 到完成，防止被 GC 取消
_BACKGROUND_TASKS: set = set()


def _spawn_background(coro):
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


async def _ingest_document_background(kb_id: str, doc_id: str, user_id: str) -> None:
    """审核通过后异步摄入：切分+向量化+ES+图谱，回写处理任务进度。

    ponytail: 不阻塞 approve 请求（大文档同步摄入会触发网关 504）；
    独立 DB 会话 + 单例依赖，失败隔离，不污染主请求事务。
    """
    async with AsyncSessionLocal() as db:
        doc = await db.scalar(
            select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
        )
        if doc is None:
            return
        ingester = DocumentIngester(
            get_embedder(),
            settings.RAG_CHUNK_SIZE,
            settings.RAG_CHUNK_OVERLAP,
            settings.RAG_CHUNK_MIN_CHARS,
            es=get_es(),
            graph=GraphStore(get_llm(), get_embedder()),
        )
        task = await db.scalar(
            select(DocumentTask)
            .where(DocumentTask.document_id == doc.id)
            .order_by(DocumentTask.created_at.desc())
        )
        try:
            await ingester.ingest_existing(doc, db)
            if task is not None:
                task.status = "completed"
                task.progress = 100
                task.current_step = "完成"
                task.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as e:  # noqa: BLE001  (intentional catch-all: background ingest task, log and skip on failure)
            logger.warning("background ingest failed kb=%s doc=%s: %s", kb_id, doc_id, e)
            if task is not None:
                task.status = "failed"
                task.current_step = "摄入失败"
                await db.commit()


@router.post("/knowledge-bases/{kb_id}/documents/{doc_id}/approve", response_model=DocumentOut)
async def approve_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_kb_access("edit")),
):
    """审核通过：翻转状态为已审核，并触发摄入（切分+向量化+ES+图谱）。

    方案 A 的核心入口：上传时只落库不摄入，检索侧天然隔离未审核内容；
    这里才真正把文档纳入检索库。幂等：已是「已审核」直接返回，不重复摄入。
    """
    doc = await db.scalar(select(Document).where(Document.id == doc_id, Document.kb_id == kb_id))
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if doc.status == "已审核":
        return doc_out(doc)  # 幂等：已审核不再重复摄入

    doc.status = "已审核"
    doc.reviewed_at = datetime.now(timezone.utc)
    doc.reviewed_by = str(user.id)
    doc.parse_status = "done"  # P0：审核通过即解析完成
    await db.flush()

    # 处理任务：进入处理中（前端据此推进进度条）
    task = await db.scalar(
        select(DocumentTask)
        .where(DocumentTask.document_id == doc.id)
        .order_by(DocumentTask.created_at.desc())
    )
    if task is not None:
        task.status = "processing"
        task.progress = 50
        task.current_step = "向量化中"
        task.started_at = datetime.now(timezone.utc)

    # 触发摄入：先 commit（status=已审核 + task=processing 落库）再调度摄入 ——
    # 摄入任务用独立 DB 会话，若先调度后提交，可能读到未提交的旧状态。
    # 生产走后台异步不阻塞请求（大文档同步摄入会触发网关 504）；
    # ponytail: 测试环境同步摄入，避免依赖后台任务调度时序（CI 冷启动
    # postgres 较慢，原 3s 轮询超时会导致测试偶发失败）。
    await db.commit()  # 持久化 status=已审核 + task=processing，前端立即可见进度
    if settings.APP_ENV == "test":
        await _ingest_document_background(kb_id, doc.id, str(user.id))
    else:
        _spawn_background(_ingest_document_background(kb_id, doc.id, str(user.id)))

    await db.refresh(doc)
    await record_operation(db, user, "approve", related_doc_id=str(doc.id), detail=doc.title)
    return doc_out(doc)


@router.post("/knowledge-bases/{kb_id}/documents/{doc_id}/reject", response_model=DocumentOut)
async def reject_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_kb_access("edit")),
):
    """审核驳回：状态改为已拒绝，保留原始文件与解析文本留痕，但不摄入（不进检索库）。"""
    doc = await db.scalar(select(Document).where(Document.id == doc_id, Document.kb_id == kb_id))
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    doc.status = "已拒绝"
    doc.reviewed_at = datetime.now(timezone.utc)
    doc.reviewed_by = str(user.id)
    doc.parse_status = "failed"  # P0：驳回即解析失败（不进检索库）
    # 处理任务：标记为失败（已驳回）
    task = await db.scalar(
        select(DocumentTask)
        .where(DocumentTask.document_id == doc.id)
        .order_by(DocumentTask.created_at.desc())
    )
    if task is not None:
        task.status = "failed"
        task.current_step = "已驳回"
        task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(doc)
    await record_operation(db, user, "reject", related_doc_id=str(doc.id), detail=doc.title)
    return doc_out(doc)


@router.post("/knowledge-bases/{kb_id}/documents/{doc_id}/ai-review", response_model=AIReviewOut)
async def ai_review_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    embedder: EmbeddingModel = Depends(get_embedder),
    llm: OpenAICompatProvider = Depends(get_llm),
    _: User = Depends(require_kb_access("view")),
):
    """AI 辅助审核：相似度检索 + LLM 结构化建议。只读分析，不写库。"""
    from app.core.rag.ai_review import ai_review_document as _review

    result = await _review(kb_id, doc_id, db, embedder, llm)
    if result is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    # 对齐 Pydantic camelCase 输出
    return {
        "verdict": result["verdict"],
        "summary": result["summary"],
        "duplicates": result["duplicates"],
        "outdatedFindings": result["outdated_findings"],
        "qualityNotes": result["quality_notes"],
        "suggestedKb": result["suggested_kb"],
        "similarityFindings": [
            {
                "similarity": f["similarity"],
                "docTitle": f["docTitle"],
                "docId": f["docId"],
                "snippet": f["snippet"],
                "matchedChunk": f["matchedChunk"],
            }
            for f in result.get("similarity_findings", [])
        ],
    }
