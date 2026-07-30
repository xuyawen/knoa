"""知识图谱接口 — 读取 + 编辑（CRUD / 合并 / 溯源 / 缺口信号）。

读取：查询 kg_node / kg_edge，可选 kb_id 过滤单库，limit 防超大规模拖垮前端。
写入：创建/修改/删除实体和关系、合并同义实体。写操作要求 KB edit 权限，
合并/删除要求 admin。所有写操作主动失效图检索缓存。

关键设计：
- 实体以 (kb_id, label) 去重，边端点也按 (kb_id, label) 解析，
  避免跨库同名实体被错误连边；
- stats（nodeCount/edgeCount/typeCounts/kbCount）按「过滤后的全集」聚合，
  不受渲染采样 limit 截断影响，大图谱下统计依然准确；
- 边查询用 from_label/to_label IN (节点 labels) 预筛，避免边表全表加载。
"""
import asyncio
import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import Select, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, get_accessible_kb_ids, get_kb_permission_level
from app.core.graph import GraphStore, _invalidate_graph
from app.core.pagination import paginate
from app.database import AsyncSessionLocal
from app.db import DocChunk, Document, KGEdge, KGGapSignal, KGNode, KnowledgeBase, User
from app.deps import get_db, get_embedder, get_llm

logger = logging.getLogger(__name__)

router = APIRouter()

# 后台图谱重建任务引用集：持有 task 到完成，防止被 GC 取消（与 review.py 同款机制）
_REBUILD_TASKS: set = set()
# 重建进度（kb_id -> {total, processed, status}），供前端轮询展示「已处理 X/N 篇」。
# 进程内状态：running/done/failed；无条目视为 idle。
_REBUILD_PROGRESS: dict[str, dict[str, Any]] = {}


def _node_out(n: KGNode) -> dict[str, Any]:
    return {
        "id": str(n.id),
        "label": n.label,
        "type": n.type,
        "kbId": n.kb_id,
        "chunkId": str(n.chunk_id) if n.chunk_id else None,
        "createdAt": n.created_at.isoformat() if n.created_at else None,
    }


def _edge_out(e: KGEdge, id_by_key: dict[tuple[str, str], str]) -> dict[str, Any] | None:
    """按 (kb_id, label) 解析边端点为节点 id — 跨库同名实体互不串扰。"""
    s = id_by_key.get((e.kb_id, e.from_label))
    t = id_by_key.get((e.kb_id, e.to_label))
    if not (s and t):
        return None
    return {"id": str(e.id), "source": s, "target": t, "relation": e.relation}


def _parse_iso(v: str | None, name: str) -> datetime | None:
    """解析 ISO 8601 查询参数；非法输入返回 400 而非让数据库抛 500。"""
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"参数 {name} 需为 ISO 8601 时间，如 2026-07-01T00:00:00+00:00"
        ) from None


def _base_node_q(
    kb_id: str | None,
    allowed: list[str],
    node_type: str | None,
    biz_category: str | None,
    dt_from: datetime | None,
    dt_to: datetime | None,
    q: str | None = None,
) -> Select:
    """带全部筛选条件的节点基础查询。

    恒内联 knowledge_base（kb_id 为外键、KB.id 为主键，不会增减行数），
    以便同一查询派生 subquery 复用于 count / group_by / 全集 label 采集。
    q 非空时追加实体名称模糊过滤（ilike，大小写不敏感）。
    """
    stmt = select(KGNode).join(KnowledgeBase, KnowledgeBase.id == KGNode.kb_id)
    stmt = stmt.where(KGNode.kb_id == kb_id if kb_id else KGNode.kb_id.in_(allowed))
    if node_type:
        stmt = stmt.where(KGNode.type == node_type)
    if biz_category:
        stmt = stmt.where(KnowledgeBase.category == biz_category)
    if dt_from:
        stmt = stmt.where(KGNode.created_at >= dt_from)
    if dt_to:
        stmt = stmt.where(KGNode.created_at <= dt_to)
    if q:
        stmt = stmt.where(KGNode.label.ilike(f"%{q.strip()}%"))
    return stmt


def _edge_kb_scope(q: Select, kb_id: str | None, allowed: list[str]) -> Select:
    """给边查询附加 KB 可见范围（RBAC）。"""
    return q.where(KGEdge.kb_id == kb_id if kb_id else KGEdge.kb_id.in_(allowed))


@router.get("/graph")
async def get_graph(
    kb_id: str | None = Query(default=None, description="按知识库过滤；不传返回全部"),
    node_type: str | None = Query(default=None, description="按实体类别过滤（KGNode.type）"),
    biz_category: str | None = Query(default=None, description="按知识库业务分类过滤（knowledge_base.category）"),
    from_date: str | None = Query(default=None, alias="from", description="created_at >= 该日期（ISO，含）"),
    to_date: str | None = Query(default=None, alias="to", description="created_at <= 该日期（ISO，含）"),
    limit: int = Query(default=500, ge=1, le=3000, description="最多返回节点数"),
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
) -> dict[str, Any]:
    """返回图谱节点/边 + 统计。node_type/biz_category/from/to 真正参与查询。

    nodes/edges 是「渲染采样」（节点按 limit 截断，边只保留两端都在采样内的）；
    stats 是同一筛选条件下的「全集聚合」，不受 limit 影响。
    """
    # RBAC：按用户可见 KB 范围过滤，避免越权读取全公司图谱
    allowed = await get_accessible_kb_ids(db, _current)
    if kb_id and kb_id not in allowed:
        raise HTTPException(status_code=403, detail="无权访问该知识库的图谱")
    dt_from = _parse_iso(from_date, "from")
    dt_to = _parse_iso(to_date, "to")

    base = _base_node_q(kb_id, allowed, node_type, biz_category, dt_from, dt_to)
    sub = base.subquery()

    # 渲染采样：最近 limit 个节点
    nodes = list((await db.scalars(base.order_by(KGNode.created_at.desc()).limit(limit))).all())

    # 全集统计：与渲染采样同筛选条件，但不受 limit 截断
    node_total = int(await db.scalar(select(func.count()).select_from(sub)) or 0)
    kb_total = int(await db.scalar(select(func.count(func.distinct(sub.c.kb_id)))) or 0)
    type_rows = (await db.execute(select(sub.c.type, func.count()).group_by(sub.c.type))).all()
    type_counts: dict[str, int] = {str(t or "未知"): int(c) for t, c in type_rows}
    # 过滤后全集实体 (kb_id, label) — 用于统计「两端都在全集内」的边数
    full_keys = {
        (r.kb_id, r.label)
        for r in (await db.execute(select(sub.c.kb_id, sub.c.label))).all()
    }

    # 渲染边：按节点 label 预筛避免边表全表扫描，再只保留两端都在采样内的
    id_by_key = {(n.kb_id, n.label): str(n.id) for n in nodes}
    labels = {n.label for n in nodes}
    out_edges: list[dict[str, Any]] = []
    if labels:
        edge_q = _edge_kb_scope(select(KGEdge), kb_id, allowed).where(
            or_(KGEdge.from_label.in_(labels), KGEdge.to_label.in_(labels))
        )
        for e in (await db.scalars(edge_q)).all():
            o = _edge_out(e, id_by_key)
            if o:
                out_edges.append(o)

    # 全集边数：轻量列查询（不加载 ORM 整行），两端都在全集实体集内才计数
    edge_total = 0
    if full_keys:
        full_labels = {lbl for _, lbl in full_keys}
        cnt_q = _edge_kb_scope(
            select(KGEdge.kb_id, KGEdge.from_label, KGEdge.to_label), kb_id, allowed
        ).where(or_(KGEdge.from_label.in_(full_labels), KGEdge.to_label.in_(full_labels)))
        edge_total = sum(
            1
            for r in (await db.execute(cnt_q)).all()
            if (r.kb_id, r.from_label) in full_keys and (r.kb_id, r.to_label) in full_keys
        )

    return {
        "nodes": [_node_out(n) for n in nodes],
        "edges": out_edges,
        "stats": {
            "nodeCount": node_total,
            "edgeCount": edge_total,
            "kbCount": kb_total,
            "typeCounts": type_counts,
        },
    }


@router.get("/graph/nodes")
async def list_graph_nodes(
    kb_id: str | None = Query(default=None, description="按知识库过滤；不传返回全部"),
    node_type: str | None = Query(default=None, description="按实体类别过滤（KGNode.type）"),
    q: str | None = Query(default=None, description="按实体名称模糊搜索（大小写不敏感）"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=15, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
) -> dict[str, Any]:
    """节点管理表格的分页列表 — 真·全集分页，不受画布渲染采样 limit 限制。

    与 GET /api/graph 共用同一套过滤/RBAC 逻辑（_base_node_q）；只返回当前页节点 + total，
    不计算边/stats（那些是画布渲染数据，表格不需要），翻页开销恒定。
    """
    allowed = await get_accessible_kb_ids(db, _current)
    if kb_id and kb_id not in allowed:
        raise HTTPException(status_code=403, detail="无权访问该知识库的图谱")
    base = _base_node_q(kb_id, allowed, node_type, None, None, None, q)
    rows, total = await paginate(db, base.order_by(KGNode.created_at.desc(), KGNode.id), page=page, page_size=page_size)
    return {"items": [_node_out(r[0]) for r in rows], "total": total}


@router.get("/graph/hot-nodes")
async def graph_hot_nodes(
    kb_id: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """热门实体 TopN：按度数（被关系边引用次数）近似热度。

    度数按 (kb_id, label) 聚合，跨库同名实体不合并；边只查轻量列。
    """
    allowed = await get_accessible_kb_ids(db, _current)
    if kb_id and kb_id not in allowed:
        raise HTTPException(status_code=403, detail="无权访问该知识库的图谱")
    node_q = select(KGNode)
    if kb_id:
        node_q = node_q.where(KGNode.kb_id == kb_id)
    else:
        node_q = node_q.where(KGNode.kb_id.in_(allowed))
    nodes = list((await db.scalars(node_q)).all())

    degree: dict[tuple[str, str], int] = {}
    edge_q = _edge_kb_scope(
        select(KGEdge.kb_id, KGEdge.from_label, KGEdge.to_label), kb_id, allowed
    )
    for r in (await db.execute(edge_q)).all():
        degree[(r.kb_id, r.from_label)] = degree.get((r.kb_id, r.from_label), 0) + 1
        degree[(r.kb_id, r.to_label)] = degree.get((r.kb_id, r.to_label), 0) + 1

    ranked = sorted(nodes, key=lambda n: degree.get((n.kb_id, n.label), 0), reverse=True)[:limit]
    return [{**_node_out(n), "degree": degree.get((n.kb_id, n.label), 0)} for n in ranked]


@router.get("/graph/recent")
async def graph_recent_nodes(
    kb_id: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """最近更新实体 TopN：按 created_at 倒序。"""
    allowed = await get_accessible_kb_ids(db, _current)
    if kb_id and kb_id not in allowed:
        raise HTTPException(status_code=403, detail="无权访问该知识库的图谱")
    node_q = select(KGNode).order_by(KGNode.created_at.desc()).limit(limit)
    if kb_id:
        node_q = node_q.where(KGNode.kb_id == kb_id)
    else:
        node_q = node_q.where(KGNode.kb_id.in_(allowed))
    nodes = list((await db.scalars(node_q)).all())
    return [_node_out(n) for n in nodes]


@router.get("/graph/export")
async def graph_export(
    kb_id: str | None = Query(default=None),
    fmt: str = Query(default="json", pattern="^(json|gexf)$"),
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
) -> JSONResponse:
    """导出完整图谱 {nodes, edges}。json 直接返回；gexf 返回 GEXF XML 供 Gephi 等。"""
    allowed = await get_accessible_kb_ids(db, _current)
    if kb_id and kb_id not in allowed:
        raise HTTPException(status_code=403, detail="无权访问该知识库的图谱")
    node_q = select(KGNode)
    edge_q = select(KGEdge)
    if kb_id:
        node_q = node_q.where(KGNode.kb_id == kb_id)
        edge_q = edge_q.where(KGEdge.kb_id == kb_id)
    else:
        node_q = node_q.where(KGNode.kb_id.in_(allowed))
        edge_q = edge_q.where(KGEdge.kb_id.in_(allowed))
    nodes = list((await db.scalars(node_q)).all())
    edges = list((await db.scalars(edge_q)).all())

    id_by_key = {(n.kb_id, n.label): str(n.id) for n in nodes}
    out_nodes = [_node_out(n) for n in nodes]
    out_edges = []
    for e in edges:
        o = _edge_out(e, id_by_key)
        if o:
            out_edges.append(o)

    if fmt == "gexf":
        xml = _to_gexf(out_nodes, out_edges)
        # 必须用 Response：JSONResponse 会把 XML 字符串再 JSON 编码一层，产出损坏文件
        return Response(
            content=xml,
            media_type="application/xml; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="graph.gexf"'},
        )
    return JSONResponse(
        content={
            "exportedAt": datetime.now(timezone.utc).isoformat(),
            "nodes": out_nodes,
            "edges": out_edges,
        },
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="graph.json"'},
    )


def _to_gexf(nodes: list[dict], edges: list[dict]) -> str:
    """把 {nodes,edges} 序列化成 GEXF XML（Gephi 可读）。"""
    node_xml = []
    for n in nodes:
        node_xml.append(
            f'    <node id="{n["id"]}" label="{_xml(n["label"])}">'
            f'<attvalues><attvalue for="type" value="{_xml(n["type"] or "")}"/>'
            f'<attvalue for="kbId" value="{_xml(n["kbId"])}"/></attvalues></node>'
        )
    edge_xml = []
    for i, e in enumerate(edges):
        edge_xml.append(
            f'    <edge id="e{i}" source="{e["source"]}" target="{e["target"]}" '
            f'label="{_xml(e["relation"])}"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gexf xmlns="http://gexf.net/1.3" version="1.3">\n'
        '  <graph mode="static" defaultedgetype="directed">\n'
        '    <nodes>\n' + "\n".join(node_xml) + "\n    </nodes>\n"
        '    <edges>\n' + "\n".join(edge_xml) + "\n    </edges>\n"
        "  </graph>\n</gexf>"
    )


def _xml(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ======================================================================
# Phase 1: 实体溯源
# ======================================================================


@router.get("/graph/nodes/{node_id}/source")
async def graph_node_source(
    node_id: str,
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
) -> dict[str, Any]:
    """返回实体节点的源文档/chunk 信息，供前端溯源跳转。"""
    try:
        nid = _uuid.UUID(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的节点 ID") from None
    node = await db.get(KGNode, nid)
    if not node:
        raise HTTPException(status_code=404, detail="实体不存在")
    # 权限：用户必须能访问该 KB
    allowed = await get_accessible_kb_ids(db, _current)
    if node.kb_id not in allowed:
        raise HTTPException(status_code=403, detail="无权访问该知识库")
    # 查 chunk + 文档
    chunk = await db.get(DocChunk, node.chunk_id) if node.chunk_id else None
    if not chunk:
        return {"docId": None, "docTitle": None, "kbId": node.kb_id, "chunkContent": None, "chunkIndex": None}
    doc = await db.get(Document, chunk.document_id)
    return {
        "docId": str(chunk.document_id),
        "docTitle": doc.title if doc else None,
        "kbId": node.kb_id,
        "chunkContent": chunk.content[:1000] if chunk.content else None,
        "chunkIndex": chunk.chunk_index,
    }


# ======================================================================
# Phase 2: 图谱编辑 CRUD + 合并
# ======================================================================


class _NodeCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    type: str | None = Field(default=None, max_length=50)
    kb_id: str = Field(..., alias="kbId")
    chunk_id: str | None = Field(default=None, alias="chunkId")

    model_config = {"populate_by_name": True}


class _NodeUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    type: str | None = Field(default=None, max_length=50)


class _EdgeCreate(BaseModel):
    from_id: str = Field(..., alias="fromId")
    to_id: str = Field(..., alias="toId")
    relation: str = Field(..., min_length=1, max_length=100)

    model_config = {"populate_by_name": True}


class _MergeRequest(BaseModel):
    kb_id: str = Field(..., alias="kbId")
    source_ids: list[str] = Field(..., alias="sourceIds", min_length=1)
    target_label: str = Field(..., alias="targetLabel", min_length=1, max_length=200)
    target_type: str | None = Field(default=None, alias="targetType", max_length=50)

    model_config = {"populate_by_name": True}


async def _require_kb_write(db: AsyncSession, user: User, kb_id: str, level: str = "edit") -> None:
    """校验用户对指定 KB 的写权限，不足则 403。"""
    user_level = await get_kb_permission_level(db, kb_id, user)
    from app.core.security import LEVEL_ORDER
    if user_level is None or LEVEL_ORDER.get(user_level, 0) < LEVEL_ORDER.get(level, 0):
        raise HTTPException(status_code=403, detail=f"需要该知识库的 {level} 权限")


@router.post("/graph/nodes", status_code=201)
async def create_graph_node(
    body: _NodeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """创建实体节点。同 KB 同 label 已存在则 409。"""
    await _require_kb_write(db, user, body.kb_id, "edit")
    # 去重检查
    existing = await db.scalar(
        select(KGNode.id).where(KGNode.kb_id == body.kb_id, KGNode.label == body.label)
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"实体 '{body.label}' 已存在")
    # chunk_id 可选：不传则取该 KB 任意一个 chunk（占位）
    chunk_id = None
    if body.chunk_id:
        chunk_id = _uuid.UUID(body.chunk_id)
    else:
        chunk_id = await db.scalar(select(DocChunk.id).where(DocChunk.kb_id == body.kb_id).limit(1))
    if not chunk_id:
        raise HTTPException(status_code=400, detail="该知识库无任何文档 chunk，无法创建实体")
    # 向量化 label（复用 embedder）
    from app.deps import get_embedder
    embedder = get_embedder()
    embedding = (await embedder.embed([body.label]))[0]
    node = KGNode(
        kb_id=body.kb_id,
        label=body.label,
        type=body.type,
        chunk_id=chunk_id,
        embedding=embedding,
    )
    db.add(node)
    # 必须 commit：get_db 请求结束只 close（未提交即回滚），仅 flush 不会落库。
    # commit 隐含 flush（node.id 已分配），expire_on_commit=False 保证 _node_out 仍可读。
    await db.commit()
    _invalidate_graph(body.kb_id)
    return _node_out(node)


@router.put("/graph/nodes/{node_id}")
async def update_graph_node(
    node_id: str,
    body: _NodeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """修改实体的 label / type。"""
    try:
        nid = _uuid.UUID(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的节点 ID") from None
    node = await db.get(KGNode, nid)
    if not node:
        raise HTTPException(status_code=404, detail="实体不存在")
    await _require_kb_write(db, user, node.kb_id, "edit")
    old_label = node.label
    if body.label is not None and body.label != node.label:
        # 检查新 label 不重复
        dup = await db.scalar(
            select(KGNode.id).where(KGNode.kb_id == node.kb_id, KGNode.label == body.label)
        )
        if dup:
            raise HTTPException(status_code=409, detail=f"实体 '{body.label}' 已存在")
        node.label = body.label
        # 同步更新边的 from_label / to_label
        await db.execute(
            update(KGEdge).where(KGEdge.kb_id == node.kb_id, KGEdge.from_label == old_label)
            .values(from_label=body.label)
        )
        await db.execute(
            update(KGEdge).where(KGEdge.kb_id == node.kb_id, KGEdge.to_label == old_label)
            .values(to_label=body.label)
        )
        # 重新向量化
        from app.deps import get_embedder
        embedder = get_embedder()
        node.embedding = (await embedder.embed([body.label]))[0]
    if body.type is not None:
        node.type = body.type
    await db.commit()
    _invalidate_graph(node.kb_id)
    return _node_out(node)


@router.delete("/graph/nodes/{node_id}", status_code=204)
async def delete_graph_node(
    node_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """删除实体（级联删除关联边）。需要 admin 权限。"""
    try:
        nid = _uuid.UUID(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的节点 ID") from None
    node = await db.get(KGNode, nid)
    if not node:
        raise HTTPException(status_code=404, detail="实体不存在")
    await _require_kb_write(db, user, node.kb_id, "admin")
    # 级联删边
    await db.execute(
        delete(KGEdge).where(
            KGEdge.kb_id == node.kb_id,
            or_(KGEdge.from_label == node.label, KGEdge.to_label == node.label),
        )
    )
    await db.delete(node)
    await db.commit()
    _invalidate_graph(node.kb_id)


@router.get("/graph/edges")
async def list_graph_edges(
    kb_id: str | None = Query(default=None, description="按知识库过滤；不传返回全部"),
    relation: str | None = Query(default=None, description="按关系类型过滤（KGEdge.relation）"),
    q: str | None = Query(default=None, description="模糊搜索关系名/源实体/目标实体（大小写不敏感）"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=15, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
) -> dict[str, Any]:
    """关系检索表格的分页列表 — 真·全集分页，不受画布渲染采样 limit 限制。

    与 GET /api/graph 共用 RBAC 逻辑（_edge_kb_scope）；q 同时匹配关系名/源实体/目标实体。
    只返回当前页边 + total，items 直接携带源/目标 label（表格展示用，无需再查节点）。
    """
    allowed = await get_accessible_kb_ids(db, _current)
    if kb_id and kb_id not in allowed:
        raise HTTPException(status_code=403, detail="无权访问该知识库的图谱")
    stmt = _edge_kb_scope(select(KGEdge), kb_id, allowed)
    if relation:
        stmt = stmt.where(KGEdge.relation == relation)
    if q:
        pat = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(KGEdge.relation.ilike(pat), KGEdge.from_label.ilike(pat), KGEdge.to_label.ilike(pat))
        )
    rows, total = await paginate(db, stmt.order_by(KGEdge.created_at.desc(), KGEdge.id), page=page, page_size=page_size)
    return {
        "items": [
            {
                "id": str(e.id),
                "sourceLabel": e.from_label,
                "targetLabel": e.to_label,
                "relation": e.relation,
                "kbId": e.kb_id,
            }
            for (e,) in rows
        ],
        "total": total,
    }


@router.post("/graph/edges", status_code=201)
async def create_graph_edge(
    body: _EdgeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """创建关系边。两端节点必须存在且同 KB。"""
    try:
        from_id = _uuid.UUID(body.from_id)
        to_id = _uuid.UUID(body.to_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的节点 ID") from None
    from_node = await db.get(KGNode, from_id)
    to_node = await db.get(KGNode, to_id)
    if not from_node or not to_node:
        raise HTTPException(status_code=404, detail="端点实体不存在")
    if from_node.kb_id != to_node.kb_id:
        raise HTTPException(status_code=400, detail="不能跨知识库建立关系")
    await _require_kb_write(db, user, from_node.kb_id, "edit")
    # 去重
    dup = await db.scalar(
        select(KGEdge.id).where(
            KGEdge.kb_id == from_node.kb_id,
            KGEdge.from_label == from_node.label,
            KGEdge.to_label == to_node.label,
            KGEdge.relation == body.relation,
        )
    )
    if dup:
        raise HTTPException(status_code=409, detail="该关系已存在")
    edge = KGEdge(
        kb_id=from_node.kb_id,
        from_label=from_node.label,
        to_label=to_node.label,
        relation=body.relation,
    )
    db.add(edge)
    await db.commit()
    _invalidate_graph(from_node.kb_id)
    return {"id": str(edge.id), "source": str(from_node.id), "target": str(to_node.id), "relation": edge.relation}


@router.delete("/graph/edges/{edge_id}", status_code=204)
async def delete_graph_edge(
    edge_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """删除关系边。需要 admin 权限。"""
    try:
        eid = _uuid.UUID(edge_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的边 ID") from None
    edge = await db.get(KGEdge, eid)
    if not edge:
        raise HTTPException(status_code=404, detail="关系不存在")
    await _require_kb_write(db, user, edge.kb_id, "admin")
    await db.delete(edge)
    await db.commit()
    _invalidate_graph(edge.kb_id)


async def _load_merge_sources(db: AsyncSession, kb_id: str, source_ids: list[str]) -> list[KGNode]:
    """加载合并源节点并校验：无效 ID → 400；一个都找不到 → 404；
    查回数少于请求数（不存在 / 跨库）→ 400。绝不静默丢弃。"""
    source_uuids = []
    for sid in source_ids:
        try:
            source_uuids.append(_uuid.UUID(sid))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的节点 ID: {sid}") from None
    sources = list((await db.execute(
        select(KGNode).where(KGNode.id.in_(source_uuids), KGNode.kb_id == kb_id)
    )).scalars().all())
    if not sources:
        raise HTTPException(status_code=404, detail="未找到源实体")
    if len(sources) != len(set(source_uuids)):
        raise HTTPException(
            status_code=400,
            detail="部分源实体不存在或不属于该知识库，请仅合并同一知识库内的实体",
        )
    return sources


async def _merge_plan(
    db: AsyncSession, kb_id: str, sources: list[KGNode], target_label: str,
) -> dict[str, Any]:
    """只读计算合并影响：模拟边重定向 → 自环删除 → 去重，给出各项变更计数。

    预览接口与实际合并共用这一套规则，保证“所见即所得”；
    合并端点先执行它、再应用变更，并将其作为结果摘要返回。
    """
    source_labels = {n.label for n in sources}
    target_exists = await db.scalar(
        select(KGNode.id).where(KGNode.kb_id == kb_id, KGNode.label == target_label)
    ) is not None

    # 端点命中 source_labels 或 target_label 的所有边——恰是合并会波及的全集
    candidates = list((await db.execute(
        select(KGEdge).where(
            KGEdge.kb_id == kb_id,
            or_(
                KGEdge.from_label.in_(source_labels | {target_label}),
                KGEdge.to_label.in_(source_labels | {target_label}),
            ),
        )
    )).scalars().all())

    redirected = 0
    self_loops = 0
    groups: dict[tuple[str, str, str], int] = {}
    for e in candidates:
        nf = target_label if e.from_label in source_labels else e.from_label
        nt = target_label if e.to_label in source_labels else e.to_label
        if nf == nt:  # 重定向后变成自环 → 删除
            self_loops += 1
            continue
        if nf != e.from_label or nt != e.to_label:
            redirected += 1
        key = (nf, nt, e.relation)
        groups[key] = groups.get(key, 0) + 1
    duplicates = sum(c - 1 for c in groups.values() if c > 1)

    src_types = sorted({n.type for n in sources if n.type})
    return {
        "targetExists": target_exists,
        "nodesRemoved": sum(1 for n in sources if n.label != target_label),
        "edgesRedirected": redirected,
        "selfLoopsRemoved": self_loops,
        "duplicateEdgesRemoved": duplicates,
        "sourceTypes": src_types,
        "typeConflict": len(src_types) > 1,
    }


class _MergePreviewRequest(BaseModel):
    kb_id: str = Field(..., alias="kbId")
    source_ids: list[str] = Field(..., alias="sourceIds", min_length=1)
    target_label: str = Field(..., alias="targetLabel", min_length=1, max_length=200)

    model_config = {"populate_by_name": True}


@router.post("/graph/merge/preview")
async def preview_merge(
    body: _MergePreviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """合并预览：只读计算合并影响（将删除几个实体、重定向/删除几条边），不写入。

    供用户选好实体、输入目标名后，在确认前于弹窗里展示“会发生什么”。
    """
    await _require_kb_write(db, user, body.kb_id, "admin")
    sources = await _load_merge_sources(db, body.kb_id, body.source_ids)
    plan = await _merge_plan(db, body.kb_id, sources, body.target_label)
    return {"sources": [_node_out(n) for n in sources], "targetLabel": body.target_label, **plan}


@router.post("/graph/merge")
async def merge_graph_nodes(
    body: _MergeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """合并多个同义实体为一个 target。边重定向，源节点删除。需要 admin。

    返回结构化摘要（字段与 preview 一致），供前端明确告知用户发生了什么。
    """
    await _require_kb_write(db, user, body.kb_id, "admin")
    sources = await _load_merge_sources(db, body.kb_id, body.source_ids)
    # 先只读算影响、再执行；预览与结果摘要共用同一套规则
    plan = await _merge_plan(db, body.kb_id, sources, body.target_label)
    source_labels = {n.label for n in sources}

    # 查找或创建 target
    target = await db.scalar(
        select(KGNode).where(KGNode.kb_id == body.kb_id, KGNode.label == body.target_label)
    )
    if not target:
        # 新建 target：向量必须对应 target_label 重新计算——不能沿用第一个源节点的向量，
        # 否则合并后节点“名向量不匹配”（向量是源节点 label 的），拉低 Graph RAG 余弦选种质量；
        # 与 editNode 改 label 后重算 embedding 的行为保持一致
        first = sources[0]
        embedder = get_embedder()
        target_embedding = (await embedder.embed([body.target_label]))[0]
        target = KGNode(
            kb_id=body.kb_id,
            label=body.target_label,
            type=body.target_type or first.type,
            chunk_id=first.chunk_id,
            embedding=target_embedding,
        )
        db.add(target)
        await db.flush()
    else:
        if body.target_type:
            target.type = body.target_type

    # 重定向边：from_label / to_label 在 source_labels 中的 → 改为 target_label
    # 排除自环（target 指向 target）
    await db.execute(
        update(KGEdge)
        .where(KGEdge.kb_id == body.kb_id, KGEdge.from_label.in_(source_labels))
        .values(from_label=body.target_label)
    )
    await db.execute(
        update(KGEdge)
        .where(KGEdge.kb_id == body.kb_id, KGEdge.to_label.in_(source_labels))
        .values(to_label=body.target_label)
    )
    # 删除自环边（from == to == target_label）
    await db.execute(
        delete(KGEdge).where(
            KGEdge.kb_id == body.kb_id,
            KGEdge.from_label == body.target_label,
            KGEdge.to_label == body.target_label,
        )
    )
    # 删除重复边（同 from+to+relation 只保留一条）
    # 简化处理：加载所有 target 相关边，内存去重
    related_edges = list((await db.execute(
        select(KGEdge).where(
            KGEdge.kb_id == body.kb_id,
            or_(KGEdge.from_label == body.target_label, KGEdge.to_label == body.target_label),
        )
    )).scalars().all())
    seen_triples: set[tuple[str, str, str]] = set()
    for e in related_edges:
        key = (e.from_label, e.to_label, e.relation)
        if key in seen_triples:
            await db.delete(e)
        else:
            seen_triples.add(key)

    # 删除源节点（不包含 target 本身）
    for s in sources:
        if s.label != body.target_label:
            await db.delete(s)
    # 先 commit 再失效缓存：避免 commit 前缓存被并发 GET 重新填回旧数据
    await db.commit()
    _invalidate_graph(body.kb_id)
    return {"merged": len(sources), "target": _node_out(target), **plan}


# ======================================================================
# Phase 4: 知识缺口信号
# ======================================================================


@router.get("/graph/gaps")
async def get_graph_gaps(
    kb_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """知识缺口列表：按问题聚合频次，返回 Top N。"""
    allowed = await get_accessible_kb_ids(db, _current)
    q = select(
        KGGapSignal.question,
        KGGapSignal.kb_id,
        func.count(KGGapSignal.id).label("count"),
        func.max(KGGapSignal.created_at).label("last_at"),
    ).group_by(KGGapSignal.question, KGGapSignal.kb_id)
    if kb_id:
        if kb_id not in allowed:
            raise HTTPException(status_code=403, detail="无权访问该知识库")
        q = q.where(KGGapSignal.kb_id == kb_id)
    else:
        q = q.where(KGGapSignal.kb_id.in_(allowed))
    q = q.order_by(func.count(KGGapSignal.id).desc()).limit(limit)
    rows = (await db.execute(q)).all()
    return [
        {
            "question": r.question,
            "kbId": r.kb_id,
            "count": r.count,
            "lastAt": r.last_at.isoformat() if r.last_at else None,
        }
        for r in rows
    ]


@router.delete("/graph/gaps", status_code=204)
async def clear_graph_gaps(
    kb_id: str | None = Query(default=None),
    question: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
) -> None:
    """标记缺口已处理（删除记录）。可按 kb_id + question 精确删，或不传参清空全部可见。"""
    allowed = await get_accessible_kb_ids(db, _current)
    q = delete(KGGapSignal)
    if kb_id:
        if kb_id not in allowed:
            raise HTTPException(status_code=403, detail="无权访问该知识库")
        q = q.where(KGGapSignal.kb_id == kb_id)
    else:
        q = q.where(KGGapSignal.kb_id.in_(allowed))
    if question:
        q = q.where(KGGapSignal.question == question)
    await db.execute(q)
    await db.commit()


# ---------------------------------------------------------------------------
# 图谱重建（存量已审核文档补抽 / 换模型后全量重抽）
# ---------------------------------------------------------------------------
async def _rebuild_graph_background(kb_id: str, clean: bool) -> None:
    """后台重建某 KB 图谱：独立会话，对该库已审核文档的 chunk 重新 LLM 抽取。

    用于补「脚本直写 DB（graph=None）/ 早期抽取静默失败」导致的空图。
    clean=True 先清空本库节点+边再重抽（真重建）；False 走 extract 的 label 去重增量补全。
    失败隔离：单篇文档抽取异常不影响其余文档与主流程。
    进度写入 _REBUILD_PROGRESS，供 /graph/rebuild/status 轮询。
    """
    _REBUILD_PROGRESS[kb_id] = {"total": 0, "processed": 0, "status": "running"}
    try:
        async with AsyncSessionLocal() as db:
            store = GraphStore(get_llm(), get_embedder())
            if clean:
                await db.execute(delete(KGEdge).where(KGEdge.kb_id == kb_id))
                await db.execute(delete(KGNode).where(KGNode.kb_id == kb_id))
                await db.commit()
                _invalidate_graph(kb_id)
            docs = (
                await db.execute(
                    select(Document.id, Document.title).where(
                        Document.kb_id == kb_id, Document.status == "已审核"
                    )
                )
            ).all()
            prog = _REBUILD_PROGRESS[kb_id]
            prog["total"] = len(docs)
            for doc_id, title in docs:
                try:
                    chunks = (
                        await db.execute(
                            select(DocChunk).where(DocChunk.document_id == doc_id).order_by(
                                DocChunk.chunk_index
                            )
                        )
                    ).scalars().all()
                    infos = [
                        {"index": c.chunk_index, "content": c.content, "chunk_id": c.id}
                        for c in chunks
                    ]
                    if infos:
                        await store.extract(kb_id, title, infos, db)
                        await db.commit()
                except Exception as e:  # noqa: BLE001  (best-effort: 单篇失败跳过，继续其余文档)
                    logger.warning("rebuild graph doc=%s failed: %s", title, e)
                    await db.rollback()
                finally:
                    prog["processed"] += 1
            # 重建收尾：统一清理零度落单节点（单篇抽取的轮内清理只管当轮新建节点，
            # 跨文档级联场景的落单节点由这里兜底）
            pruned = await store.prune_isolated_nodes(db, kb_id)
            await db.commit()
            if pruned:
                logger.info("rebuild graph kb=%s: pruned %d isolated nodes", kb_id, pruned)
            _invalidate_graph(kb_id)
        _REBUILD_PROGRESS[kb_id]["status"] = "done"
    except Exception as e:  # noqa: BLE001  (整体崩溃：清库/会话异常，标记 failed 供前端提示)
        logger.warning("rebuild graph kb=%s crashed: %s", kb_id, e)
        if kb_id in _REBUILD_PROGRESS:
            _REBUILD_PROGRESS[kb_id]["status"] = "failed"


@router.post("/graph/rebuild", status_code=202)
async def rebuild_graph(
    kb_id: str = Query(...),
    clean: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """重建知识库图谱：对该库已审核文档的 chunk 重新 LLM 抽取实体/关系。

    - clean=false（默认）：增量补全，已有实体按 label 去重跳过，适合给存量空图补数据；
    - clean=true：先清空本库节点+边再全量重抽，适合换抽取模型后彻底重建。
    需 KB admin 权限（重抽会批量写图、清图属破坏性操作）。后台异步执行，立即返回待处理文档数。
    """
    await _require_kb_write(db, user, kb_id, "admin")
    doc_count = await db.scalar(
        select(func.count(Document.id)).where(
            Document.kb_id == kb_id, Document.status == "已审核"
        )
    )
    task = asyncio.create_task(_rebuild_graph_background(kb_id, clean))
    _REBUILD_TASKS.add(task)
    task.add_done_callback(_REBUILD_TASKS.discard)
    return {"kbId": kb_id, "queuedDocs": doc_count or 0, "clean": clean}


@router.get("/graph/rebuild/status")
async def rebuild_status(
    kb_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询某 KB 图谱重建进度（前端轮询用）。

    返回 status：running（进行中，附 total/processed）/ done / failed / idle（无任务）。
    进度为进程内状态，服务重启后重置为 idle。
    """
    allowed = await get_accessible_kb_ids(db, user)
    if kb_id not in allowed:
        raise HTTPException(status_code=403, detail="无权访问该知识库的图谱")
    prog = _REBUILD_PROGRESS.get(kb_id)
    if prog is None:
        return {"kbId": kb_id, "status": "idle", "total": 0, "processed": 0}
    return {
        "kbId": kb_id,
        "status": prog["status"],
        "total": prog["total"],
        "processed": prog["processed"],
    }
