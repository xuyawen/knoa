"""通用响应模型。"""
from typing import Generic, TypeVar

from app.models.knowledge import CamelModel

T = TypeVar("T")


class PaginatedOut(CamelModel, Generic[T]):
    """统一分页响应（items / total / page / pageSize / pages）。"""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
