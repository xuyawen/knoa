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
    tags: list[str] = []
    category: str | None = None


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
    kb_id: str | None = None   # KB UUID（前端点查看详情用）
    title: str
    doc_id: str | None = None  # 文档 UUID（前端点查看详情用）
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
    total: int = 0
    page: int = 1
    page_size: int = 20
    pages: int = 1


# ── AI 辅助审核 ──────────────────────────────────────────────


class AIReviewFindingOut(CamelModel):
    """单条相似度发现"""
    similarity: float
    doc_title: str
    doc_id: str
    snippet: str
    matched_chunk: str


class AIReviewOut(CamelModel):
    verdict: str                      # approve | reject | manual_review
    summary: str                      # 一句话总结
    duplicates: list[str]             # 重复风险
    outdated_findings: list[str]      # 过时信息
    quality_notes: list[str]          # 质量建议
    suggested_kb: str | None          # 建议归属库
    similarity_findings: list[AIReviewFindingOut]  # 相似度详情


class DocumentOut(CamelModel):
    id: str
    title: str
    type: str          # 'MD' | 'TXT' | 'DOCX' | 'PDF'
    size_kb: float
    status: str         # '已审核' | '待复核' | '已拒绝'
    updated_at: str
    original_filename: str | None = None
    file_size: int | None = None
    tags: list[str] = []
    category: str | None = None
    department_id: str | None = None
    uploader_name: str | None = None       # P0：真实上传人（冗余显示名）
    scope: str = "public"                  # P0：权限范围 private|department|company|public
    parse_status: str = "pending"          # P0：解析状态 pending|parsing|done|failed


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
    file_url: str | None = None       # OSS 直传后的可访问地址（前端直传 OSS 时回传）
    tags: list[str] | None = None          # 标签（架构图1 标签体系）
    category: str | None = None             # 分类
    department_id: str | None = None        # 归属部门（架构图2/5 部门隔离）
    scope: str | None = "public"            # P0：权限范围 private|department|company|public


class KBCreateIn(CamelModel):
    name: str
    icon: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    category: str | None = None


class KBUpdateIn(CamelModel):
    """编辑知识库：只更新调用方提供的字段（其余保持不变）。"""
    name: str | None = None
    icon: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    category: str | None = None


class KBReorderIn(CamelModel):
    """拖拽排序：前端把当前列表的完整 id 顺序传回，后端按数组下标赋 order。"""
    ordered_ids: list[str]


class KBBatchDeleteIn(CamelModel):
    """批量删除知识库：ids 为待删库 id 列表。"""
    ids: list[str]


class DocumentTaskOut(CamelModel):
    """文档处理任务（架构图6：异步处理状态跟踪，前端轮询进度条）。"""
    id: str
    document_id: str | None = None
    kb_id: str | None = None
    filename: str | None = None
    status: str                      # pending | processing | completed | failed
    progress: int = 0               # 0-100
    current_step: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str
    document_title: str | None = None


class SearchDocOut(CamelModel):
    """全局文档搜索结果项（智能搜索页文档卡片）。"""
    id: str
    title: str
    type: str
    status: str
    updated_at: str
    kb_id: str
    kb_name: str
    category: str | None = None
    scope: str = "public"
    uploader_name: str | None = None
    snippet: str
