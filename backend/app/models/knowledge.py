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
    kb: str
    title: str
    snippet: str
    confidence: float


class KnowledgeBasesResponse(CamelModel):
    knowledge_bases: list[KnowledgeBaseOut]
    health: list[HealthItemOut]
