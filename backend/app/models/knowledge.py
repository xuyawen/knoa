from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """camelCase 输出, 对齐前端 TS 接口"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class KnowledgeBaseOut(CamelModel):
    id: str
    name: str
    icon: str
    badge: str | None = None
    badge_type: str | None = None
    document_count: int = 0
    pending_count: int = 0
    description: str | None = None


class HealthItemOut(CamelModel):
    kb: str
    doc_count: int
    updated_at: str
    review_rate: float          # 审核率 = 已审核文档 / 总文档
    retrievable_rate: float     # 可检索率 = 有向量的文档 / 总文档
    freshness_hours: float | None  # 最近更新距现在小时，None=无文档
    health_score: float         # 综合健康分 = 审核率*0.4 + 可检索率*0.4 + 新鲜度分*0.2


class TrendingItemOut(CamelModel):
    question: str
    count: int


class SourceItemOut(CamelModel):
    id: int
    chunk_id: str
    kb: str
    title: str
    snippet: str
    confidence: float
    source_type: str = "kb"   # 'kb' | 'web'
    url: str | None = None      # 联网来源的原始链接


class SourceDetailOut(CamelModel):
    id: str
    title: str
    kb: str
    content: str
    chunk_index: int


class KnowledgeBasesResponse(CamelModel):
    knowledge_bases: list[KnowledgeBaseOut]
    health: list[HealthItemOut]


class DocumentOut(CamelModel):
    id: str
    title: str
    type: str          # 'MD' | 'TXT' | 'DOCX' | 'PDF'
    size_kb: float
    status: str         # '已审核' | '待复核' | '已拒绝'
    updated_at: str
    original_filename: str | None = None
    file_size: int | None = None


class DocumentDetailOut(CamelModel):
    id: str
    title: str
    type: str          # 'MD' | 'TXT' | 'DOCX' | 'PDF'
    status: str         # '已审核' | '待复核' | '已拒绝'
    content_md: str    # 解析后的全文，详情/预览/审核查看用
    original_filename: str | None = None
    file_size: int | None = None
    updated_at: str
    reviewed_at: str | None = None
    reviewed_by: str | None = None


class DocumentUploadIn(CamelModel):
    filename: str
    content: str | None = None       # 文本路径（md/txt 直传文本，向后兼容）
    content_b64: str | None = None    # 二进制路径（docx/pdf 传 base64 原始字节）


class KBCreateIn(CamelModel):
    name: str
    icon: str | None = None
    description: str | None = None


class KBUpdateIn(CamelModel):
    """编辑知识库：只更新调用方提供的字段（其余保持不变）。"""
    name: str | None = None
    icon: str | None = None
    description: str | None = None


class KBReorderIn(CamelModel):
    """拖拽排序：前端把当前列表的完整 id 顺序传回，后端按数组下标赋 order。"""
    ordered_ids: list[str]


class KBBatchDeleteIn(CamelModel):
    """批量删除知识库：ids 为待删库 id 列表。"""
    ids: list[str]
