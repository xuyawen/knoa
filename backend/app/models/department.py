from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """camelCase 输出, 对齐前端 TS 接口（与 models/knowledge.py 同款）。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DepartmentOut(CamelModel):
    id: str
    name: str
    parent_id: str | None = None
    description: str | None = None
    sort_order: int = 0
    created_at: datetime


class DepartmentNode(DepartmentOut):
    """树节点：children 递归嵌套（架构图2 部门树）。"""

    children: list["DepartmentNode"] = []


DepartmentNode.model_rebuild()


class DepartmentCreateIn(CamelModel):
    name: str
    parent_id: str | None = None
    description: str | None = None
    sort_order: int = 0


class DepartmentUpdateIn(CamelModel):
    name: str | None = None
    parent_id: str | None = None
    description: str | None = None
    sort_order: int | None = None


class DepartmentReorderIn(CamelModel):
    """同级部门拖拽排序：传入某父级（或顶级 None）下的完整有序 id 列表。"""
    parent_id: str | None = None
    ids: list[str]
