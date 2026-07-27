"""SQLAlchemy 异步分页工具。"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def paginate(
    db: AsyncSession,
    stmt,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list, int]:
    """对任意 select 语句做计数 + 分页，返回 (rows, total)。

    rows 是 Result.all() 的结果；单实体调用方用 `[r[0] for r in rows]` 解包，
    多表 join 返回 tuple 的调用方按需解包即可。
    兼容层钳制：多数路由已用 Query(ge/le) 校验，未校验的调用方在这里兑底，
    防止 page<=0 产生负 offset（SQL 报错）或超大 page_size 拖垮数据库。
    """
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.scalar(count_stmt)) or 0
    rows = (
        await db.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        )
    ).all()
    return rows, total
