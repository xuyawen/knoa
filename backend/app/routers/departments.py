"""架构图2/5 部门 CRUD（文档权限隔离的部门维度）。

GET 任意登录用户可用（前端按部门筛选需要树）；写操作仅 admin。
删除带子部门或仍有归属文档时阻止，避免级联丢数据/外键报错。
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_permission
from app.core.rbac import Perm
from app.db import Department, Document, User
from app.deps import get_db
from app.models.department import (
    DepartmentCreateIn,
    DepartmentNode,
    DepartmentOut,
    DepartmentReorderIn,
    DepartmentUpdateIn,
)

router = APIRouter()

MAX_DEPT_DEPTH = 3  # 部门最多 3 级：顶级 / 二级 / 三级


def _dept_index(depts: list[Department]) -> dict[str, Department]:
    return {str(x.id): x for x in depts}


def _depth(depts_by_id: dict[str, Department], dept_id: str) -> int:
    """某部门自身的层级（根部门=1）。"""
    depth = 0
    seen: set[str] = set()
    cur: str | None = dept_id
    while cur in depts_by_id and cur not in seen:
        seen.add(cur)
        depth += 1
        p = depts_by_id[cur].parent_id
        cur = str(p) if p else None
    return depth


def _subtree_height(depts_by_id: dict[str, Department], root_id: str) -> int:
    """以 root_id 为根的子树最大深度（root 自身=1）。"""
    children_map: dict[str, list[Department]] = {}
    for x in depts_by_id.values():
        children_map.setdefault(str(x.parent_id), []).append(x)
    max_d = 1
    stack: list[tuple[str, int]] = [(root_id, 1)]
    while stack:
        cid, cd = stack.pop()
        for c in children_map.get(cid, []):
            nd = cd + 1
            if nd > max_d:
                max_d = nd
            stack.append((str(c.id), nd))
    return max_d



def _to_out(d: Department) -> DepartmentOut:
    return DepartmentOut(
        id=str(d.id),
        name=d.name,
        parent_id=str(d.parent_id) if d.parent_id else None,
        description=d.description,
        sort_order=d.sort_order,
        created_at=d.created_at,
    )


def _build_tree(depts: list[Department]) -> list[DepartmentNode]:
    """扁平 Department 列表 → 嵌套树，按 sort_order 排序。"""
    nodes = {
        str(d.id): DepartmentNode(
            id=str(d.id),
            name=d.name,
            parent_id=str(d.parent_id) if d.parent_id else None,
            description=d.description,
            sort_order=d.sort_order,
            created_at=d.created_at,
            children=[],
        )
        for d in depts
    }
    roots: list[DepartmentNode] = []
    for d in depts:
        node = nodes[str(d.id)]
        parent = nodes.get(str(d.parent_id)) if d.parent_id else None
        if parent is not None:
            parent.children.append(node)
        else:
            roots.append(node)

    def sort_rec(ns: list[DepartmentNode]) -> None:
        ns.sort(key=lambda n: n.sort_order)
        for n in ns:
            sort_rec(n.children)

    sort_rec(roots)
    return roots


@router.get("/departments", response_model=list[DepartmentNode])
async def list_departments(
    db: AsyncSession = Depends(get_db),
    _: Department = Depends(get_current_user),
):
    depts = (await db.execute(select(Department).order_by(Department.sort_order))).scalars().all()
    return _build_tree(list(depts))


@router.post("/departments", response_model=DepartmentOut, status_code=201)
async def create_department(
    payload: DepartmentCreateIn,
    db: AsyncSession = Depends(get_db),
    _: Department = Depends(require_permission(Perm.SYS_SETTINGS)),
):
    parent_id = None
    if payload.parent_id:
        parent = await db.scalar(select(Department).where(Department.id == uuid.UUID(payload.parent_id)))
        if parent is None:
            raise HTTPException(status_code=400, detail="父部门不存在")
        parent_id = uuid.UUID(payload.parent_id)
        # 深度上限：新部门层级 = 父部门层级 + 1，不得超过 MAX_DEPT_DEPTH
        all_depts = (await db.execute(select(Department))).scalars().all()
        idx = _dept_index(all_depts)
        parent_level = _depth(idx, str(parent_id))
        if parent_level + 1 > MAX_DEPT_DEPTH:
            raise HTTPException(
                status_code=400,
                detail=f"部门最多支持 {MAX_DEPT_DEPTH} 级，所选父部门已是第 {parent_level} 级，无法再向下创建",
            )
    d = Department(
        name=payload.name,
        parent_id=parent_id,
        description=payload.description,
        sort_order=payload.sort_order,
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return _to_out(d)


@router.patch("/departments/{dept_id}", response_model=DepartmentOut)
async def update_department(
    dept_id: str,
    payload: DepartmentUpdateIn,
    db: AsyncSession = Depends(get_db),
    _: Department = Depends(require_permission(Perm.SYS_SETTINGS)),
):
    d = await db.scalar(select(Department).where(Department.id == uuid.UUID(dept_id)))
    if d is None:
        raise HTTPException(status_code=404, detail="部门不存在")
    # 改父级时做环检测：新父不能是自己或自己的后代
    if payload.parent_id is not None:
        if not payload.parent_id:
            d.parent_id = None
        else:
            pid = uuid.UUID(payload.parent_id)
            if pid == d.id:
                raise HTTPException(status_code=400, detail="不能把部门设为自己的父级")
            all_depts = (await db.execute(select(Department))).scalars().all()
            children_map: dict[str, list] = {}
            for x in all_depts:
                children_map.setdefault(str(x.parent_id), []).append(x)
            # 收集 d 的所有后代
            desc: set[str] = set()
            stack = list(children_map.get(str(d.id), []))
            while stack:
                c = stack.pop()
                desc.add(str(c.id))
                stack.extend(children_map.get(str(c.id), []))
            if str(pid) in desc:
                raise HTTPException(status_code=400, detail="不能将部门挂到自己的子部门下")
            if not any(str(x.id) == str(pid) for x in all_depts):
                raise HTTPException(status_code=400, detail="父部门不存在")
            # 深度上限：调整后「d 自身新层级 + d 现有子树高度」不得超过 MAX_DEPT_DEPTH，
            # 否则把 d 挂到更深层父级会连带子/孙部门一起突破层级上限。
            idx = _dept_index(all_depts)
            subtree_h = _subtree_height(idx, str(d.id))
            new_parent_depth = _depth(idx, str(pid)) if pid else 0
            if new_parent_depth + subtree_h > MAX_DEPT_DEPTH:
                raise HTTPException(
                    status_code=400,
                    detail=f"部门最多支持 {MAX_DEPT_DEPTH} 级，调整后将超过层级上限",
                )
            d.parent_id = pid
    if payload.name is not None:
        d.name = payload.name
    if payload.description is not None:
        d.description = payload.description
    if payload.sort_order is not None:
        d.sort_order = payload.sort_order
    await db.commit()
    await db.refresh(d)
    return _to_out(d)


@router.post("/departments/reorder", status_code=200)
async def reorder_departments(
    payload: DepartmentReorderIn,
    db: AsyncSession = Depends(get_db),
    _: Department = Depends(require_permission(Perm.SYS_SETTINGS)),
):
    """同级部门拖拽排序：传入某父级（或顶级 None）下的完整有序 id 列表，按序重设 sort_order。

    仅允许同级内重排，不改父级、不触碰层级深度。
    """
    parent_id = uuid.UUID(payload.parent_id) if payload.parent_id else None
    stmt = select(Department)
    if parent_id is None:
        stmt = stmt.where(Department.parent_id.is_(None))
    else:
        stmt = stmt.where(Department.parent_id == parent_id)
    children = (await db.execute(stmt)).scalars().all()
    existing = {str(c.id) for c in children}
    incoming = set(payload.ids)
    if incoming != existing:
        raise HTTPException(
            status_code=400,
            detail="排序列表必须包含该层级下的全部部门（不可遗漏或混入其他层级）",
        )
    by_id = {str(c.id): c for c in children}
    for idx, did in enumerate(payload.ids):
        by_id[did].sort_order = idx
    await db.commit()
    return {"ok": True}


@router.delete("/departments/{dept_id}", status_code=204)
async def delete_department(
    dept_id: str,
    db: AsyncSession = Depends(get_db),
    _: Department = Depends(require_permission(Perm.SYS_SETTINGS)),
):
    d = await db.scalar(select(Department).where(Department.id == uuid.UUID(dept_id)))
    if d is None:
        raise HTTPException(status_code=404, detail="部门不存在")
    child_cnt = await db.scalar(
        select(func.count()).select_from(Department).where(Department.parent_id == d.id)
    )
    if child_cnt:
        raise HTTPException(status_code=400, detail="该部门下有子部门，无法删除")
    doc_cnt = await db.scalar(
        select(func.count()).select_from(Document).where(Document.department_id == d.id)
    )
    if doc_cnt:
        raise HTTPException(status_code=400, detail="该部门下仍有文档，无法删除")
    user_cnt = await db.scalar(
        select(func.count()).select_from(User).where(User.department_id == d.id)
    )
    if user_cnt:
        raise HTTPException(status_code=400, detail="该部门下仍有用户，无法删除")
    await db.delete(d)
    await db.commit()
