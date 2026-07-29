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
    _is_kb_super_admin,
    dept_ancestors,
    require_kb_access,
    require_permission,
    get_current_user,
)
from app.core.storage import get_object_store
from app.db import Department, DocChunk, Document, DocumentTask, KBDeptGrant, KBPermission, KnowledgeBase, User
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


class KBDeptGrantItem(CamelModel):
    deptId: str
    level: str  # view | edit | admin


class KBDeptGrantsUpdate(CamelModel):
    grants: list[KBDeptGrantItem]


class KBDeptGrantOut(CamelModel):
    id: str
    deptId: str
    deptName: str
    level: str


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
    q: str | None = Query(None, max_length=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 按 order 列排序（拖拽持久化），同序再按创建时间稳定
    stmt = select(KnowledgeBase).order_by(KnowledgeBase.order, KnowledgeBase.created_at)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            KnowledgeBase.name.ilike(pattern) | KnowledgeBase.category.ilike(pattern)
        )
    result = await db.execute(stmt)
    kbs = result.scalars().all()

    # 库级权限：一次性聚合查询，替代原先「每库调一次 get_kb_permission_level」的 N+1
    # 合并语义：个人显式优先 → 部门继承 → 开放库兜底 / 严格库拒绝。
    perm_map: dict[str, str] = {}
    strict_kbs: set[str] = set()
    is_super = await _is_kb_super_admin(db, user)
    if not is_super:
        kb_ids = [kb.id for kb in kbs]
        # 1) 个人授权
        perms = (
            await db.execute(
                select(KBPermission).where(
                    KBPermission.kb_id.in_(kb_ids),
                    KBPermission.user_id == user.id,
                )
            )
        ).scalars().all()
        personal_map: dict[str, str] = {}
        for p in perms:
            cur = personal_map.get(p.kb_id)
            if cur is None or LEVEL_ORDER.get(p.level, 0) > LEVEL_ORDER.get(cur, 0):
                personal_map[p.kb_id] = p.level
        # 2) 部门授权（沿祖先链批量查）
        dept_map: dict[str, str] = {}
        if user.department_id:
            ancestors = await dept_ancestors(db, user.department_id)
            dept_rows = (
                await db.execute(
                    select(KBDeptGrant).where(
                        KBDeptGrant.kb_id.in_(kb_ids),
                        KBDeptGrant.dept_id.in_(ancestors),
                    )
                )
            ).scalars().all()
            for g in dept_rows:
                cur = dept_map.get(g.kb_id)
                if cur is None or LEVEL_ORDER.get(g.level, 0) > LEVEL_ORDER.get(cur, 0):
                    dept_map[g.kb_id] = g.level
        # 3) 合并：个人优先，否则部门最高
        for kid in kb_ids:
            if kid in personal_map:
                perm_map[kid] = personal_map[kid]
            elif kid in dept_map:
                perm_map[kid] = dept_map[kid]
        # 4) 严格库集合：存在任意授权记录（个人或部门）的库
        any_rows = (
            await db.execute(
                select(KBPermission.kb_id).where(KBPermission.kb_id.in_(kb_ids))
            )
        ).scalars().all()
        any_dept_rows = (
            await db.execute(
                select(KBDeptGrant.kb_id).where(KBDeptGrant.kb_id.in_(kb_ids))
            )
        ).scalars().all()
        strict_kbs = set(any_rows) | set(any_dept_rows)

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
        if not is_super and kb.id not in perm_map and kb.id in strict_kbs:
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
        category=kb.category,
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
    if payload.category is not None:
        kb.category = payload.category
    await db.commit()
    await db.refresh(kb)
    return KnowledgeBaseOut(
        id=kb.id, name=kb.name, icon=kb.icon, description=kb.description,
        category=kb.category,
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
    # admin 校验：个人 admin 或 部门 admin 任一存在即通过
    has_admin = any(lv == "admin" for lv in seen.values())
    if not has_admin:
        dept_admin = await db.scalar(
            select(KBDeptGrant.id).where(
                KBDeptGrant.kb_id == kb_id, KBDeptGrant.level == "admin"
            ).limit(1)
        )
        has_admin = dept_admin is not None
    if not has_admin:
        raise HTTPException(status_code=400, detail="知识库至少需保留一名 admin 成员（个人或部门）")
    await db.execute(delete(KBPermission).where(KBPermission.kb_id == kb_id))
    for uid, lv in seen.items():
        db.add(KBPermission(kb_id=kb_id, user_id=uid, level=lv))
    await db.commit()
    return {"members": await _kb_members(db, kb_id)}


@router.get("/knowledge-bases/{kb_id}/dept-grants", response_model=dict)
async def list_kb_dept_grants(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("admin")),
):
    """列出某知识库的部门授权记录（库 admin 或全局 admin 可见）。"""
    rows = (
        await db.execute(
            select(KBDeptGrant, Department)
            .join(Department, Department.id == KBDeptGrant.dept_id)
            .where(KBDeptGrant.kb_id == kb_id)
        )
    ).all()
    grants = [
        KBDeptGrantOut(
            id=str(g.id),
            deptId=str(g.dept_id),
            deptName=d.name,
            level=g.level,
        ).model_dump(by_alias=True)
        for g, d in rows
    ]
    return {"grants": grants}


@router.put("/knowledge-bases/{kb_id}/dept-grants", response_model=dict)
async def set_kb_dept_grants(
    kb_id: str,
    payload: KBDeptGrantsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("admin")),
):
    """覆盖式设置某 KB 的部门授权。库 admin 或全局 admin 可操作。

    - deptId 必须存在；level 须为 view/edit/admin。
    - 同一部门按最高级别去重。
    """
    seen: dict[uuid.UUID, str] = {}
    for g in payload.grants:
        try:
            did = uuid.UUID(g.deptId)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"非法的 deptId: {g.deptId}") from None
        if g.level not in LEVEL_ORDER:
            raise HTTPException(status_code=400, detail=f"非法的权限级别: {g.level}")
        if did not in seen or LEVEL_ORDER[g.level] > LEVEL_ORDER[seen[did]]:
            seen[did] = g.level
    # 校验部门存在
    for did in seen:
        dept = (
            await db.execute(select(Department).where(Department.id == did))
        ).scalar_one_or_none()
        if dept is None:
            raise HTTPException(status_code=400, detail=f"部门不存在: {did}")
    await db.execute(delete(KBDeptGrant).where(KBDeptGrant.kb_id == kb_id))
    for did, lv in seen.items():
        db.add(KBDeptGrant(kb_id=kb_id, dept_id=did, level=lv))
    await db.commit()
    # 返回最新列表
    return await list_kb_dept_grants(kb_id, db=db, _=_)


class EffectiveMemberOut(CamelModel):
    userId: str
    username: str
    displayName: str | None = None
    level: str
    source: str  # "direct" | "dept:部门名"


@router.get("/knowledge-bases/{kb_id}/effective-members", response_model=dict)
async def list_kb_effective_members(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_kb_access("admin")),
):
    """预览某 KB 的有效权限合并结果（个人 + 部门继承），带来源标签。

    合并语义：个人显式优先——有个人记录用个人的，否则取部门继承。
    """
    # 1) 个人授权
    personal_rows = (
        await db.execute(
            select(KBPermission, User)
            .join(User, User.id == KBPermission.user_id)
            .where(KBPermission.kb_id == kb_id)
        )
    ).all()
    # 个人最高级别去重
    personal_map: dict[uuid.UUID, tuple[str, User]] = {}
    for p, u in personal_rows:
        cur = personal_map.get(u.id)
        if cur is None or LEVEL_ORDER.get(p.level, 0) > LEVEL_ORDER.get(cur[0], 0):
            personal_map[u.id] = (p.level, u)

    # 2) 部门授权 → 展开到用户（一次性加载部门树，避免 N+1）
    dept_grant_rows = (
        await db.execute(
            select(KBDeptGrant, Department)
            .join(Department, Department.id == KBDeptGrant.dept_id)
            .where(KBDeptGrant.kb_id == kb_id)
        )
    ).all()
    # 全量拉取部门树，内存建 children map
    all_depts = (await db.execute(select(Department.id, Department.parent_id))).all()
    children_map: dict[uuid.UUID | None, list[uuid.UUID]] = {}
    for did, pid in all_depts:
        children_map.setdefault(pid, []).append(did)

    def _descendants(dept_id: uuid.UUID) -> list[uuid.UUID]:
        """BFS 求后代部门（含自身），复用内存 children_map。"""
        result: list[uuid.UUID] = []
        stack = [dept_id]
        seen: set[uuid.UUID] = set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            result.append(cur)
            stack.extend(children_map.get(cur, []))
        return result

    # 按部门展开找用户，个人优先
    dept_user_map: dict[uuid.UUID, tuple[str, str, User]] = {}  # uid -> (level, dept_name, user)
    # 收集所有授权部门的后代 id，一次性查用户
    grant_descendants: list[tuple[str, str, list[uuid.UUID]]] = []  # (level, dept_name, desc_ids)
    all_desc_ids: set[uuid.UUID] = set()
    for g, dept in dept_grant_rows:
        desc = _descendants(g.dept_id)
        grant_descendants.append((g.level, dept.name, desc))
        all_desc_ids.update(desc)
    # 单次查询所有相关部门的用户
    users_by_dept: dict[uuid.UUID, list[User]] = {}
    if all_desc_ids:
        all_users = (
            await db.execute(
                select(User).where(User.department_id.in_(all_desc_ids))
            )
        ).scalars().all()
        for u in all_users:
            users_by_dept.setdefault(u.department_id, []).append(u)
    # 内存中分配
    for level, dept_name, desc in grant_descendants:
        for did in desc:
            for u in users_by_dept.get(did, []):
                if u.id in personal_map:
                    continue  # 个人优先，跳过
                cur = dept_user_map.get(u.id)
                if cur is None or LEVEL_ORDER.get(level, 0) > LEVEL_ORDER.get(cur[0], 0):
                    dept_user_map[u.id] = (level, dept_name, u)

    # 3) 合并输出
    members: list[dict] = []
    for _uid, (lv, u) in personal_map.items():
        members.append(
            EffectiveMemberOut(
                userId=str(u.id),
                username=u.username,
                displayName=u.display_name,
                level=lv,
                source="direct",
            ).model_dump(by_alias=True)
        )
    for _uid, (lv, dept_name, u) in dept_user_map.items():
        members.append(
            EffectiveMemberOut(
                userId=str(u.id),
                username=u.username,
                displayName=u.display_name,
                level=lv,
                source=f"dept:{dept_name}",
            ).model_dump(by_alias=True)
        )
    # 按级别降序、用户名稳定排序
    members.sort(key=lambda m: (-LEVEL_ORDER.get(m["level"], 0), m["username"]))
    return {"members": members}


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
    # 清库级权限（个人 + 部门）
    await db.execute(delete(KBPermission).where(KBPermission.kb_id == kb_id))
    await db.execute(delete(KBDeptGrant).where(KBDeptGrant.kb_id == kb_id))
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
