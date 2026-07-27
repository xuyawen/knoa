"""知识库路由包：原单文件 knowledge.py（1000+ 行）按职责拆分。

- bases.py     知识库本体：列表/创建/编辑/删除/排序/成员管理
- documents.py 文档：列表/搜索/标签/上传/详情/删除
- review.py    审核流：通过（触发摄入）/驳回/AI 辅助审核

main.py 仍以 `knowledge.router` 挂载，聚合后对外路由不变。
"""
from fastapi import APIRouter

from app.routers.knowledge import bases, documents, review

router = APIRouter()
router.include_router(bases.router)
router.include_router(documents.router)
router.include_router(review.router)
