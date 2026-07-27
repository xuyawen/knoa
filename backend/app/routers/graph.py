"""知识图谱只读接口 — 供 frontend 的「知识图谱」视图渲染真实图数据。

只读：仅查询 kg_node / kg_edge，不暴露任何写操作。可选 kb_id 过滤单库，
limit 防止超大规模拖垮前端渲染。节点按创建时间倒序取最近 limit 个，
边只保留「两端节点都在返回集内」的，避免出现悬空脏边。

关键设计：
- 实体以 (kb_id, label) 去重，边端点也按 (kb_id, label) 解析，
  避免跨库同名实体被错误连边；
- stats（nodeCount/edgeCount/typeCounts/kbCount）按「过滤后的全集」聚合，
  不受渲染采样 limit 截断影响，大图谱下统计依然准确；
- 边查询用 from_label/to_label IN (节点 labels) 预筛，避免边表全表加载。

P4 扩展：
- GET /api/graph/hot-nodes  热门实体 TopN（按度数近似热度）
- GET /api/graph/recent      最近更新实体 TopN（按 created_at）
- GET /api/graph/export      导出完整 {nodes,edges}（json / gexf）
- GET /api/graph 现真正消费 node_type / biz_category / from / to 过滤参数
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, get_accessible_kb_ids
from app.db import KGEdge, KGNode, KnowledgeBase, User
from app.deps import get_db

router = APIRouter()


def _node_out(n: KGNode) -> dict[str, Any]:
    return {
        "id": str(n.id),
        "label": n.label,
        "type": n.type,
        "kbId": n.kb_id,
        "createdAt": n.created_at.isoformat() if n.created_at else None,
    }


def _edge_out(e: KGEdge, id_by_key: dict[tuple[str, str], str]) -> dict[str, Any] | None:
    """按 (kb_id, label) 解析边端点为节点 id — 跨库同名实体互不串扰。"""
    s = id_by_key.get((e.kb_id, e.from_label))
    t = id_by_key.get((e.kb_id, e.to_label))
    if not (s and t):
        return None
    return {"source": s, "target": t, "relation": e.relation}


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
) -> Select:
    """带全部筛选条件的节点基础查询。

    恒内联 knowledge_base（kb_id 为外键、KB.id 为主键，不会增减行数），
    以便同一查询派生 subquery 复用于 count / group_by / 全集 label 采集。
    """
    q = select(KGNode).join(KnowledgeBase, KnowledgeBase.id == KGNode.kb_id)
    q = q.where(KGNode.kb_id == kb_id if kb_id else KGNode.kb_id.in_(allowed))
    if node_type:
        q = q.where(KGNode.type == node_type)
    if biz_category:
        q = q.where(KnowledgeBase.category == biz_category)
    if dt_from:
        q = q.where(KGNode.created_at >= dt_from)
    if dt_to:
        q = q.where(KGNode.created_at <= dt_to)
    return q


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
