"""知识库本体路由：列表（含健康度）/ 创建 / 编辑 / 删除（级联）/ 排序 / 成员管理。"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.graph import GraphStore
from app.core.rbac import Perm
from app.core.security import (
    LEVEL_ORDER,
    require_kb_access,
    require_permission,
    get_current_user,
)
from app.core.storage import get_object_store
from app.db import DocChunk, Document, DocumentTask, KBPermission, KnowledgeBase, User
from app.deps import get_db, get_es
from app.models.knowledge import (
    CamelModel,
    HealthItemOut,
    KBBatchDeleteIn,
    KBCreateIn,
    KBReorderIn,
    KBUpdateIn,
    KnowledgeBaseOut,
    KnowledgeBasesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class KBMemberOut(CamelModel):
    userId: str
    username: str
    displayName: str | None = None
    level: str


class KBMemberItem(CamelModel):
    userId: str
    level: str  # view | edit | admin


class KBMembersUpdate(CamelModel):
    members: list[KBMemberItem]


async def _kb_members(db: AsyncSession, kb_id: str) -> list[dict]:
    """汇总某 KB 的成员（含用户名/显示名/级别）；单次 join 查询，避免每成员一次查询的 N+1。"""
    rows = (
        await db.execute(
            select(KBPermission, User)
            .join(User, User.id == KBPermission.user_id)
            .where(KBPermission.kb_id == kb_id)
        )
    ).all()
    return [
        KBMemberOut(
            userId=str(u.id),
            username=u.username,
            displayName=u.display_name,
            level=p.level,
        ).model_dump(by_alias=True)
        for p, u in rows
    ]


@router.get("/knowledge-bases", response_model=KnowledgeBasesResponse)
async def get_knowledge_bases(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 按 order 列排序（拖拽持久化），同序再按创建时间稳定
    result = await db.execute(
        select(KnowledgeBase).order_by(KnowledgeBase.order, KnowledgeBase.created_at)
    )
    kbs = result.scalars().all()

    # 库级权限：一次性聚合查询，替代原先「每库调一次 get_kb_permission_level」的 N+1
    # （非 admin 用户下，原来每个 KB 触发 1~2 次 DB 查询）。
    # perm_map: kb_id -> 用户自身最高权限；strict_kbs: 存在任意权限记录的库（严格隔离）。
    perm_map: dict[str, str] = {}
    strict_kbs: set[str] = set()
    if user.role != "admin":
        perms = (
            await db.execute(
                select(KBPermission).where(
                    KBPermission.kb_id.in_([kb.id for kb in kbs]),
                    KBPermission.user_id == user.id,
                )
            )
        ).scalars().all()
        for p in perms:
            cur = perm_map.get(p.kb_id)
            if cur is None or LEVEL_ORDER.get(p.level, 0) > LEVEL_ORDER.get(cur, 0):
                perm_map[p.kb_id] = p.level
        any_rows = (
            await db.execute(
                select(KBPermission.kb_id).where(
                    KBPermission.kb_id.in_([kb.id for kb in kbs])
                )
            )
        ).scalars().all()
        strict_kbs = set(any_rows)

    # 一次聚合查询替代「每库 3 次查询」的 N+1 模式：
    # 按 kb_id 汇总 文档数 / 最新更新时间 / 待复核数。
    stats_rows = (
        await db.execute(
            select(
                Document.kb_id,
                func.count(Document.id).label("doc_count"),
                func.max(Document.updated_at).label("latest"),
                func.count(Document.id)
                .filter(Document.status == "待复核")
                .label("pending"),
                func.count(Document.id)
                .filter(Document.status == "已审核")
                .label("approved"),
            ).group_by(Document.kb_id)
        )
    ).all()
    stats_map = {row.kb_id: row for row in stats_rows}

    # 可检索率：统计「有至少 1 个 chunk（已向量化）的文档数」按 kb 分组。
    # 暴露「有文档但 chunker 没切进去 → 搜不到」的坑（如短文本被丢弃）。
    ret_rows = (
        await db.execute(
            select(Document.kb_id, func.count(func.distinct(Document.id)).label("ret"))
            .join(DocChunk, DocChunk.document_id == Document.id)
            .group_by(Document.kb_id)
        )
    ).all()
    ret_map = {row.kb_id: row.ret for row in ret_rows}

    kb_list = []
    health_list = []
    for kb in kbs:
        # 库级权限过滤（权限已上方一次性聚合算出，避免每库一次查询的 N+1）：
        #  - admin / 用户在 perm_map 中有记录 / 遗留开放库（无任何权限记录）→ 可见
        #  - 严格隔离库（存在他人权限记录但用户无记录）→ 不可见
        if user.role != "admin" and kb.id not in perm_map and kb.id in strict_kbs:
            continue

        stat = stats_map.get(kb.id)
        doc_count = stat.doc_count if stat else 0
        latest = stat.latest if stat else None
        pending_count = stat.pending if stat else 0
        approved_count = stat.approved if stat else 0
        retrievable_count = ret_map.get(kb.id, 0)

        # 健康度三维（取代原模糊的 coverage 单值）：
        #  审核率  = 已审核 / 总文档
        #  可检索率 = 有向量(chunk)文档 / 总文档
        #  新鲜度  = 最近更新距现在小时（无文档为 None → 新鲜度分 0）
        review_rate = round(approved_count / doc_count, 2) if doc_count > 0 else 0.0
        retrievable_rate = round(retrievable_count / doc_count, 2) if doc_count > 0 else 0.0
        if latest is not None:
            freshness_hours = round((datetime.now(timezone.utc) - latest).total_seconds() / 3600, 1)
            if freshness_hours < 24:
                freshness_score = 1.0
            elif freshness_hours < 24 * 7:
                freshness_score = 0.8
            elif freshness_hours < 24 * 30:
                freshness_score = 0.5
            elif freshness_hours < 24 * 90:
                freshness_score = 0.3
            else:
                freshness_score = 0.1
        else:
            freshness_hours = None
            freshness_score = 0.0
        # 综合健康分：审核率与可检索率各 0.4，新鲜度 0.2
        health_score = round(review_rate * 0.4 + retrievable_rate * 0.4 + freshness_score * 0.2, 2)

        badge = None
        badge_type = None
        if pending_count and pending_count > 0:
            badge = f"{pending_count} 份待复核"
            badge_type = "danger"

        kb_list.append(
            KnowledgeBaseOut(
                id=kb.id, name=kb.name, icon=kb.icon,
                badge=badge, badge_type=badge_type,
                document_count=doc_count or 0,
                pending_count=pending_count or 0,
                description=kb.description,
                tags=kb.tags or [],
                category=kb.category,
            )
        )
        health_list.append(
            HealthItemOut(
                kb=kb.name,
                doc_count=doc_count or 0,
                updated_at=latest.isoformat() if latest else "",
                review_rate=review_rate,
                retrievable_rate=retrievable_rate,
                freshness_hours=freshness_hours,
                health_score=health_score,
            )
        )

    total = len(kb_list)
    pages = max(1, (total + size - 1) // size) if total else 1
    start = (page - 1) * size
    end = start + size
    return KnowledgeBasesResponse(
        knowledge_bases=kb_list[start:end],
        health=health_list[start:end],
        total=total,
        page=page,
        page_size=size,
        pages=pages,
    )


@router.post("/knowledge-bases", response_model=KnowledgeBaseOut, status_code=201)
async def create_knowledge_base(
    payload: KBCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission(Perm.DOC_UPLOAD)),
):
    """新建知识库。创建者自动获得该库的 admin 级库级权限（隔离起点）。"""
    kb_id = f"kb_{uuid.uuid4().hex[:8]}"
    kb = KnowledgeBase(
        id=kb_id,
        name=payload.name,
        icon=payload.icon or "📚",
        description=payload.description,
    )
    if payload.tags is not None:
        kb.tags = payload.tags
    if payload.category:
        kb.category = payload.category
    # 库与创建者的 admin 权限单事务提交（一次 commit）：原先的两段提交在
    # 第二次 commit 失败时会留下「无权限记录的开放库」，对全员可见。
    # 注意：两个 mapper 间无 relationship()，UOW 不保证按 FK 依赖排序 insert，
    # 必须先 flush 父行（同事务内，非提交）再写权限行。
    db.add(kb)
    await db.flush()
    db.add(KBPermission(kb_id=kb_id, user_id=user.id, level="admin"))
    await db.commit()
    await db.refresh(kb)
    return KnowledgeBaseOut(
        id=kb.id, name=kb.name, icon=kb.icon, description=kb.description,
        tags=kb.tags or [], category=kb.category,
    )


@router.put("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(
    kb_id: str,
    payload: KBUpdateIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("admin")),
):
    """编辑知识库：更新名称 / 图标 / 描述（库 admin 级或全局 admin 可执行）。"""
    kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if payload.name is not None:
        kb.name = payload.name
    if payload.icon is not None:
        kb.icon = payload.icon
    if payload.description is not None:
        kb.description = payload.description
    if payload.tags is not None:
        kb.tags = payload.tags
    if payload.category is not None:
        kb.category = payload.category
    await db.commit()
    await db.refresh(kb)
    return KnowledgeBaseOut(
        id=kb.id, name=kb.name, icon=kb.icon, description=kb.description,
        tags=kb.tags or [], category=kb.category,
    )


@router.get("/knowledge-bases/{kb_id}/members", response_model=dict)
async def list_kb_members(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("admin")),
):
    """列出某知识库的成员及权限级别（库 admin 或全局 admin 可见）。"""
    return {"members": await _kb_members(db, kb_id)}


@router.put("/knowledge-bases/{kb_id}/members", response_model=dict)
async def set_kb_members(
    kb_id: str,
    payload: KBMembersUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("admin")),
):
    """全量设置某 KB 的成员（覆盖式）。库 admin 或全局 admin 可操作。

    - 同一用户按最高级别去重；级别须为 view/edit/admin。
    - 所有 userId 必须存在；至少需保留一名 admin，避免库被锁死无人可管。
    """
    seen: dict[uuid.UUID, str] = {}
    for m in payload.members:
        try:
            uid = uuid.UUID(m.userId)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"非法的 userId: {m.userId}") from None
        if m.level not in LEVEL_ORDER:
            raise HTTPException(status_code=400, detail=f"非法的权限级别: {m.level}")
        if uid not in seen or LEVEL_ORDER[m.level] > LEVEL_ORDER[seen[uid]]:
            seen[uid] = m.level
    for uid in seen:
        u = (
            await db.execute(select(User).where(User.id == uid))
        ).scalar_one_or_none()
        if u is None:
            raise HTTPException(status_code=400, detail=f"用户不存在: {uid}")
    if not any(lv == "admin" for lv in seen.values()):
        raise HTTPException(status_code=400, detail="知识库至少需保留一名 admin 成员")
    await db.execute(delete(KBPermission).where(KBPermission.kb_id == kb_id))
    for uid, lv in seen.items():
        db.add(KBPermission(kb_id=kb_id, user_id=uid, level=lv))
    await db.commit()
    return {"members": await _kb_members(db, kb_id)}


async def _delete_kb_cascade(db: AsyncSession, kb_id: str) -> None:
    """级联删除知识库：先清其下所有文档（chunk/ES/图谱/对象存储），
    再清库级权限与库本身。

    顺序关键：先取 chunk_id → 删图节点 → 删 DocChunk（FK 必须在删
    Document 前清）→ 删 ES → 删对象存储 → 删 Document → 删权限 → 删库。
    ES / 图谱连接失败时静默跳过，不阻断删除——生产环境 ES 偶发
    抖动不应导致删库失败，测试环境无 ES 也能跑通。
    """
    docs = (await db.execute(select(Document).where(Document.kb_id == kb_id))).scalars().all()
    store = get_object_store()
    for doc in docs:
        chunk_ids = (
            await db.execute(select(DocChunk.id).where(DocChunk.document_id == doc.id))
        ).scalars().all()
        # 删图谱节点（按 chunk_id 归属），连接失败静默跳过
        try:
            await GraphStore().delete_by_doc(db, kb_id, chunk_ids)
        except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, ignore graph delete failure)
            pass
        # 先清 DocumentTask，再清 DocChunk，最后删 Document，避免 FK 冲突
        await db.execute(delete(DocumentTask).where(DocumentTask.document_id == doc.id))
        # 删 DocChunk（FK 必须在删 Document 前清，否则违反外键）
        await db.execute(delete(DocChunk).where(DocChunk.document_id == doc.id))
        # 删 ES 索引，连接失败静默跳过
        try:
            await get_es().delete_by_doc(kb_id, str(doc.id))
        except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, ignore ES delete failure)
            pass
        # 删对象存储原始文件，缺失不阻断删除
        try:
            await store.delete(doc.source_path)
        except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, ignore object-store delete error)
            pass
        await db.delete(doc)
    # 清库级权限
    await db.execute(delete(KBPermission).where(KBPermission.kb_id == kb_id))
    # 删库本身
    await db.execute(delete(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    await db.commit()


@router.delete("/knowledge-bases/{kb_id}", status_code=204)
async def delete_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("admin")),
):
    """删除知识库：级联清理其下文档 / chunk / ES / 图谱 / 对象存储 / 库级权限。"""
    kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    await _delete_kb_cascade(db, kb_id)


@router.post("/knowledge-bases/reorder")
async def reorder_knowledge_bases(
    payload: KBReorderIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.SYS_SETTINGS)),
):
    """拖拽排序：前端传回当前列表的完整 id 顺序，后端按数组下标赋 order。

    全局排序操作无单一 kb_id，故要求 SYS_SETTINGS 权限（内置 admin 拥有）。
    """
    kbs = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(payload.ordered_ids)))
    ).scalars().all()
    pos = {kid: i for i, kid in enumerate(payload.ordered_ids)}
    for kb in kbs:
        kb.order = pos.get(kb.id, kb.order)
    await db.commit()
    return {"ok": True}


@router.post("/knowledge-bases/batch-delete", status_code=204)
async def batch_delete_knowledge_bases(
    payload: KBBatchDeleteIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.SYS_SETTINGS)),
):
    """批量删除知识库：对每个 id 走与单删相同的级联清理。"""
    for kb_id in payload.ids:
        kb = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        if kb:
            await _delete_kb_cascade(db, kb_id)
