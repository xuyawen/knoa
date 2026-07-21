"""知识图谱只读接口 — 供 frontend 的「知识图谱」视图渲染真实图数据。

只读：仅查询 kg_node / kg_edge，不暴露任何写操作。可选 kb_id 过滤单库，
limit 防止超大规模拖垮前端渲染。节点按创建时间倒序取最近 limit 个，
边只保留「两端节点都在返回集内」的，避免出现悬空脏边。
"""
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db import KGEdge, KGNode, User
from app.deps import get_db

router = APIRouter()


@router.get("/graph")
async def get_graph(
    kb_id: str | None = Query(default=None, description="按知识库过滤；不传返回全部"),
    limit: int = Query(default=500, ge=1, le=3000, description="最多返回节点数"),
    db: AsyncSession = Depends(get_db),
    _current: User = Depends(get_current_user),
) -> dict[str, Any]:
    node_q = select(KGNode).order_by(KGNode.created_at.desc()).limit(limit)
    if kb_id:
        node_q = node_q.where(KGNode.kb_id == kb_id)
    nodes = list((await db.scalars(node_q)).all())

    edge_q = select(KGEdge)
    if kb_id:
        edge_q = edge_q.where(KGEdge.kb_id == kb_id)
    edges = list((await db.scalars(edge_q)).all())

    # (kb_id, label) 是实体去重键，库内唯一 → label 可作节点索引
    id_by_label: dict[str, str] = {n.label: str(n.id) for n in nodes}

    type_counts: dict[str, int] = {}
    for n in nodes:
        t = n.type or "未知"
        type_counts[t] = type_counts.get(t, 0) + 1

    out_nodes = [
        {
            "id": str(n.id),
            "label": n.label,
            "type": n.type,
            "kbId": n.kb_id,
            "createdAt": n.created_at.isoformat() if n.created_at else None,
        }
        for n in nodes
    ]
    out_edges = []
    for e in edges:
        s = id_by_label.get(e.from_label)
        t = id_by_label.get(e.to_label)
        if s and t:  # 两端节点都在返回集内才连线
            out_edges.append({"source": s, "target": t, "relation": e.relation})

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
