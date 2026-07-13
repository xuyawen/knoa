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


class HealthItemOut(CamelModel):
    kb: str
    doc_count: int
    updated_at: str
    coverage: float


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
    status: str         # '已审核' | '待复核'
    updated_at: str


class DocumentUploadIn(CamelModel):
    filename: str
    content: str | None = None       # 文本路径（md/txt 直传文本，向后兼容）
    content_b64: str | None = None    # 二进制路径（docx/pdf 传 base64 原始字节）


class KBCreateIn(CamelModel):
    name: str
    icon: str | None = None
    description: str | None = None
