from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://knoa:knoa@localhost:5432/knoa"
    REDIS_URL: str = "redis://localhost:6379/0"
    # Embedding (OpenAI-compatible API)
    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1024
    # LLM (M3 启用)
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2000
    # 模型多模态能力开关（一期只开 image；audio/video 预留，
    # 切换不支持的模型时在 ask 路由层给清晰中文报错）。
    # Agnes agnes-2.0-flash 当前仅支持图片输入（image_url + base64 data URI）。
    MODEL_CAPABILITIES: dict = {"image": True, "audio": False, "video": False}
    # 联网搜索（web_search 工具）：优先 BoCha（中文检索更准），其次 Tavily，
    # 二者均留空则走无 key 的 DuckDuckGo HTML 兜底
    BOCHA_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    # LangSmith (M4 启用)
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "knoa"
    # RAG
    RAG_TOP_K: int = 5
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    # 噪声地板：低于该字符数且不含实质字符(CJK/字母/数字)的碎片视为噪声丢弃；
    # 但整篇都有实质内容时仍保底至少 1 个 chunk（短 FAQ / 零散笔记可检索）。
    RAG_CHUNK_MIN_CHARS: int = 10
    RRF_K: int = 60
    # Elasticsearch (Phase 2 混合检索；venv 装不了官方客户端，走 httpx 直连 REST)
    # 总开关：必须显式设 ES_ENABLED=True 才启用；ES 未就绪时保持 False，
    # 系统自动回退 pgvector，绝不因 ES 不可用而崩。
    ES_ENABLED: bool = False
    # 长期记忆（Phase 2 T4 Mem0 轻量自研版；复用 pgvector(JSONB)+numpy 余弦）
    MEMORY_ENABLED: bool = True        # 总开关：false 则完全跳过记忆抽取/召回/注入
    MEMORY_TOP_K: int = 5               # 每轮问答注入 prompt 的相关记忆条数
    MEMORY_SIM_THRESHOLD: float = 0.92  # 新记忆与旧记忆余弦相似度超此值则更新而非新增（去重/冲突消解）
    # 知识图谱 / Graph RAG（Phase 3 T1；Postgres 图存储，无需 Neo4j server）
    GRAPH_ENABLED: bool = True         # 总开关：false 则跳过建图与图检索，回退普通 RAG
    GRAPH_TOP_K: int = 5               # 每轮问答图检索召回的实体种子数（再去 1 跳扩展）
    ES_URL: str = "http://localhost:9200"
    ES_USERNAME: str = ""            # 留空 = 不启用 Basic Auth
    ES_PASSWORD: str = ""
    ES_INDEX_PREFIX: str = "kb"      # 索引名格式: {prefix}_{kb_id}
    ES_REQUEST_TIMEOUT: float = 10.0
    # 鉴权 (Phase 2 RBAC)
    JWT_SECRET: str = "dev-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440   # 24h
    PBKDF2_ITERATIONS: int = 100_000
    # 初始管理员（首次启动、且无任何用户时自动创建；生产请改 .env）
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_DISPLAY_NAME: str = "系统管理员"
    # HTTPS (TLS) — 自签证书用于本地开发；生产由 nginx 做 TLS 终止
    SSL_CERT_FILE: str = "certs/cert.pem"
    SSL_KEY_FILE: str = "certs/key.pem"
    SSL_ENABLED: bool = True           # 本地开发启用 HTTPS，生产可由 nginx 反代后关
    # 对象存储（Phase 3 T3 文档解析管线）
    # local = 落本地磁盘（沙箱/开发默认，零依赖）；s3 = MinIO/S3 兼容（httpx + 手写 SigV4）
    OBJECT_STORE: str = "local"
    OBJECT_STORE_LOCAL_DIR: str = "app/data/uploads"  # 相对项目根 backend/ 解析
    # MinIO / S3（OBJECT_STORE=s3 时生效；httpx 直连 + SigV4，无需官方 SDK）
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "knoa"
    MINIO_REGION: str = "us-east-1"
    MINIO_USE_SSL: bool = False
    # App
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
