"""架构图2/5 部门 CRUD（文档权限隔离的部门维度）。

GET 任意登录用户可用（前端按部门筛选需要树）；写操作仅 admin。
删除带子部门或仍有归属文档时阻止，避免级联丢数据/外键报错。
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db import Department, Document
from app.deps import get_db
from app.models.department import (
    DepartmentCreateIn,
    DepartmentNode,
    DepartmentOut,
    DepartmentUpdateIn,
)

router = APIRouter()


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
    _: Department = Depends(require_roles("admin")),
):
    parent_id = None
    if payload.parent_id:
        parent = await db.scalar(select(Department).where(Department.id == uuid.UUID(payload.parent_id)))
        if parent is None:
            raise HTTPException(status_code=400, detail="父部门不存在")
        parent_id = uuid.UUID(payload.parent_id)
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
    _: Department = Depends(require_roles("admin")),
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


@router.delete("/departments/{dept_id}", status_code=204)
async def delete_department(
    dept_id: str,
    db: AsyncSession = Depends(get_db),
    _: Department = Depends(require_roles("admin")),
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
    await db.delete(d)
    await db.commit()
