"""知识图谱只读接口 — 供 frontend 的「知识图谱」视图渲染真实图数据。

只读：仅查询 kg_node / kg_edge，不暴露任何写操作。可选 kb_id 过滤单库，
limit 防止超大规模拖垮前端渲染。节点按创建时间倒序取最近 limit 个，
边只保留「两端节点都在返回集内」的，避免出现悬空脏边。

P4 扩展：
- GET /api/graph/hot-nodes  热门实体 TopN（按度数近似热度）
- GET /api/graph/recent      最近更新实体 TopN（按 created_at）
- GET /api/graph/export      导出完整 {nodes,edges}（json / gexf）
- GET /api/graph 现真正消费 node_type / biz_category / from / to 过滤参数
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, get_accessible_kb_ids, require_permission
from app.core.rbac import Perm
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


def _edge_out(e: KGEdge, id_by_label: dict[str, str]) -> dict[str, Any] | None:
    s = id_by_label.get(e.from_label)
    t = id_by_label.get(e.to_label)
    if not (s and t):
        return None
    return {"source": s, "target": t, "relation": e.relation}


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
    _perm: User = Depends(require_permission(Perm.GRAPH_MANAGE)),
) -> dict[str, Any]:
    """返回图谱节点/边 + 统计。node_type/biz_category/from/to 真正参与查询。"""
    # RBAC：按用户可见 KB 范围过滤，避免越权读取全公司图谱
    allowed = await get_accessible_kb_ids(db, _current)
    if kb_id and kb_id not in allowed:
        raise HTTPException(status_code=403, detail="无权访问该知识库的图谱")
    node_q = select(KGNode)
    if kb_id:
        node_q = node_q.where(KGNode.kb_id == kb_id)
    else:
        node_q = node_q.where(KGNode.kb_id.in_(allowed))
    if node_type:
        node_q = node_q.where(KGNode.type == node_type)
    if biz_category:
        node_q = node_q.join(KnowledgeBase, KnowledgeBase.id == KGNode.kb_id).where(
            KnowledgeBase.category == biz_category
        )
    if from_date:
        node_q = node_q.where(KGNode.created_at >= from_date)
    if to_date:
        node_q = node_q.where(KGNode.created_at <= to_date)
    node_q = node_q.order_by(KGNode.created_at.desc()).limit(limit)
    nodes = list((await db.scalars(node_q)).all())

    edge_q = select(KGEdge)
    if kb_id:
        edge_q = edge_q.where(KGEdge.kb_id == kb_id)
    else:
        edge_q = edge_q.where(KGEdge.kb_id.in_(allowed))
    edges = list((await db.scalars(edge_q)).all())

    # (kb_id, label) 是实体去重键，库内唯一 → label 可作节点索引
    id_by_label: dict[str, str] = {n.label: str(n.id) for n in nodes}

    type_counts: dict[str, int] = {}
    for n in nodes:
        t = n.type or "未知"
        type_counts[t] = type_counts.get(t, 0) + 1

    out_nodes = [_node_out(n) for n in nodes]
    out_edges = []
    for e in edges:
        o = _edge_out(e, id_by_label)
        if o:
            out_edges.append(o)

    kb_ids = {n.kb_id for n in nodes}
    return {
        "nodes": out_nodes,
        "edges": out_edges,
        "stats": {
            "nodeCount": len(nodes),
            "edgeCount": len(out_edges),
            "kbCount": len(kb_ids),
            "typeCounts": type_counts,
        },
    }


@router.get("/graph/hot-nodes")
async def graph_hot_nodes(
    kb_id: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
    _perm: User = Depends(require_permission(Perm.GRAPH_MANAGE)),
) -> list[dict[str, Any]]:
    """热门实体 TopN：按度数（被关系边引用次数）近似热度。"""
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

    degree: dict[str, int] = {}
    for e in edges:
        degree[e.from_label] = degree.get(e.from_label, 0) + 1
        degree[e.to_label] = degree.get(e.to_label, 0) + 1

    ranked = sorted(nodes, key=lambda n: degree.get(n.label, 0), reverse=True)[:limit]
    return [{**_node_out(n), "degree": degree.get(n.label, 0)} for n in ranked]


@router.get("/graph/recent")
async def graph_recent_nodes(
    kb_id: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
    _perm: User = Depends(require_permission(Perm.GRAPH_MANAGE)),
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
    _perm: User = Depends(require_permission(Perm.GRAPH_MANAGE)),
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

    id_by_label: dict[str, str] = {n.label: str(n.id) for n in nodes}
    out_nodes = [_node_out(n) for n in nodes]
    out_edges = []
    for e in edges:
        o = _edge_out(e, id_by_label)
        if o:
            out_edges.append(o)

    if fmt == "gexf":
        xml = _to_gexf(out_nodes, out_edges)
        return JSONResponse(
            content=xml,
            media_type="application/xml",
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
