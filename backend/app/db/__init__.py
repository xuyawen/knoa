import hashlib
import secrets
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    icon: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 标签/分类（架构图1：标签分类系统）
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list, server_default="[]")
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # order 是 SQL 保留字；name="order" + quote=True 编译为带引号的 "order"
    order: Mapped[int] = mapped_column(Integer, name="order", default=0, server_default="0", nullable=False, quote=True)
    pending_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    documents: Mapped[list["Document"]] = relationship(back_populates="kb")


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[str] = mapped_column(ForeignKey("knowledge_base.id"))
    title: Mapped[str] = mapped_column(String(200))
    source_path: Mapped[str] = mapped_column(String(500))
    content_md: Mapped[str] = mapped_column(Text)
    # 文档状态：'已审核'(已入库/可检索) | '待复核'(用户上传待人工复核) | '已拒绝'(审核不通过)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="已审核", server_default="已审核")
    # 原始文件信息（上传即存，方案 A 延迟摄入：未审核前只落原始字节+解析文本）
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 审核留痕：approve/reject 时写入（谁、何时）
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 标签/分类/部门归属（架构图2/5：文档维度权限 + 标签体系）
    # ponytail: tags 存 JSONB 数组，department_id 自引用 department 表做部门隔离
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list, server_default="[]")
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("department.id"), nullable=True)
    # P0：真实三要素（前端不再造假）
    # 上传人：冗余 display_name 避免每次 join app_user；id 用于"我的文档"过滤
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    uploader_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 权限范围：private(仅本人) | department(部门) | company(公司) | public(公开)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="public", server_default="public")
    # 解析状态：pending(待解析) | parsing(解析中) | done(完成) | failed(失败)
    # ponytail: 与 DocumentTask.status 同步，列表展示用，避免每次 join task
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    kb: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocChunk"]] = relationship(back_populates="document")


class DocChunk(Base):
    __tablename__ = "doc_chunk"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document.id"))
    kb_id: Mapped[str] = mapped_column(ForeignKey("knowledge_base.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # ponytail: 用 JSONB 存向量, numpy 内存算余弦相似度; pgvector 留 Phase 2
    embedding: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    document: Mapped["Document"] = relationship(back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_session"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # ponytail: Phase 2 RBAC 预留
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # 对话滚动摘要：窗口外的旧对话由 LLM 压缩成的文本（长会话上下文）。
    # summarized_count 记录已被纳入摘要的历史消息条数（边界），避免重复摘要。
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summarized_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_session.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    attachments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class Trending(Base):
    __tablename__ = "trending"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(String(500))
    count: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[date] = mapped_column(Date, index=True)


class MessageFeedback(Base):
    """用户对单条回答的喜好反馈（👍/👎）。按 message_id 做 upsert。"""

    __tablename__ = "message_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_message.id"), index=True
    )
    rating: Mapped[str] = mapped_column(String(10))  # 'up' | 'down'
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    """系统用户（Phase 2 RBAC）。单公司内使用，角色分 admin/editor/viewer。"""
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 全局角色：admin(管用户+全部库) | editor(建库/传文档) | viewer(仅问答)
    role: Mapped[str] = mapped_column(String(20), default="viewer", server_default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # 系统设置：用户偏好的问答模型（透传给 ask→pipeline→agent→llm）；为空走默认
    preferred_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 语音播报开关：前端朗读按钮是否可用
    tts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # 模型配置偏好（温度/TopP/最大长度/TopK/联网/来源数/provider/人设/思考/简洁）。
    # ponytail: 服务端真值，前端不再存 localStorage；name(模型选择)走 preferred_model 列。
    model_prefs: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict, server_default="{}")
    # 用户档案字段（用户管理界面维护）
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employee_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @staticmethod
    def hash_password(password: str) -> str:
        """PBKDF2-HMAC-SHA256 + 随机 salt，依赖库 hashlib/secrets，无第三方依赖。"""
        from app.config import settings
        salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), settings.PBKDF2_ITERATIONS
        )
        return f"pbkdf2_sha256${settings.PBKDF2_ITERATIONS}${salt}${dk.hex()}"

    def verify_password(self, password: str, password_hash: str | None = None) -> bool:
        h = password_hash or self.password_hash
        try:
            _, iter_s, salt, dk = h.split("$")
            dk2 = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), bytes.fromhex(salt), int(iter_s)
            )
            return secrets.compare_digest(dk2.hex(), dk)
        except Exception:
            return False


class KBPermission(Base):
    """知识库级权限（单公司内部门间隔离）。控制某用户能否访问/编辑某 KB。

    不往 knowledge_base 表 ALTER 加 owner 列，避免无 Alembic 下的迁移麻烦；
    KB 创建者自动获得该库 level='admin' 的一条记录即可。
    """
    __tablename__ = "kb_permission"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[str] = mapped_column(ForeignKey("knowledge_base.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), index=True)
    # 库级权限：admin(管理该库) | edit(可上传/删文档) | view(仅阅读/问答)
    level: Mapped[str] = mapped_column(String(20), default="view", server_default="view")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Memory(Base):
    """用户长期记忆（Mem0 轻量自研版，Phase 2 T4 使用）。

    embedding 复用 JSONB + numpy 余弦，与 DocChunk 一致；检索时按 user_id 取
    该用户记忆做相似度排序，注入 agent prompt。
    """
    __tablename__ = "memory"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSONB)
    # 记忆类型：preference(偏好) | fact(事实) | feedback(反馈) 等，便于筛选
    meta_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KGNode(Base):
    """知识图谱节点（Phase 3 T1 Graph RAG）。

    用 Postgres 存图（不依赖 Neo4j server，沙箱起不了）。实体由 LLM 在摄入时抽取，
    embedding 复用 JSONB+numpy 余弦，与 DocChunk/Memory 同方案；检索时把问题向量
    与节点向量做余弦挑种子节点，再沿 kg_edge 做 1 跳扩展，收集相关 chunk。
    (kb_id, label) 作为实体去重键（同库同名实体只留首次出现的 chunk）。
    """
    __tablename__ = "kg_node"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[str] = mapped_column(ForeignKey("knowledge_base.id"), index=True)
    label: Mapped[str] = mapped_column(String(200))            # 实体名（如 "FBA 头程"）
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 实体类别（政策/物流/费用/流程...）
    chunk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doc_chunk.id"))  # 该实体首次出现的 chunk
    embedding: Mapped[list] = mapped_column(JSONB)             # 实体 label 的向量，检索时与问题向量算余弦
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KGEdge(Base):
    """知识图谱边（Phase 3 T1）。from_label/to_label 存实体 label 字符串（非外键），

    避免实体删除时级联复杂；连通性由 (kb_id, from_label, to_label, relation) 去重保证。
    """
    __tablename__ = "kg_edge"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[str] = mapped_column(ForeignKey("knowledge_base.id"), index=True)
    from_label: Mapped[str] = mapped_column(String(200))   # 起点实体 label
    to_label: Mapped[str] = mapped_column(String(200))     # 终点实体 label
    relation: Mapped[str] = mapped_column(String(100))     # 关系（属于 / 导致 / 需要 / 影响...）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Department(Base):
    """部门（架构图2/5：文档权限隔离的部门维度）。树形结构，parent_id 自引用。"""
    __tablename__ = "department"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))                                  # 部门名称（如"产品部"）
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("department.id"), nullable=True)  # 树形结构
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # ponytail: 关系延迟到真正需要树遍历时再补（back_populates），当前仅存 parent_id


class DocumentTask(Base):
    """文档异步处理任务（架构图6 处理管线）。上传即建 task，前端轮询进度条。

    status: pending/processing/completed/failed；progress 0-100；current_step 描述当前步骤。
    """
    __tablename__ = "document_task"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document.id"), nullable=True)
    kb_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_base.id"), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # ponytail: 状态机只这几态，落库前在代码里校验取值
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")   # 0-100 百分比
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OperationLog(Base):
    """操作日志（业务统计根数据源；best-effort 写入，绝不阻塞主流程）。"""
    __tablename__ = "operation_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action: Mapped[str] = mapped_column(String(20), index=True)  # login/upload/approve/reject/delete/ask
    related_doc_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Announcement(Base):
    """系统公告（通知中心 / 系统设置管理）。"""
    __tablename__ = "announcement"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(20), default="info", server_default="info")  # info|warn|critical
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class UserAnnouncementRead(Base):
    """公告已读记录（通知中心）。复合主键 (user_id, announcement_id) 天然去重。"""
    __tablename__ = "user_announcement_read"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    announcement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("announcement.id"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
