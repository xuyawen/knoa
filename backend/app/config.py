from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://knoa:knoa@localhost:5432/knoa"
    REDIS_URL: str = "redis://localhost:6379/0"
    # Embedding (OpenAI 兼容 API；现用阿里云百炼 text-embedding-v4，走 DashScope 兼容端点)
    EMBEDDING_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-v4"
    # v4 默认 1024 维；可选 64/128/256/512/768/1024/1536/2048。
    # 改维度时须同步改下方 _KNOWN_EMBEDDING_DIMS 并重新摄入全部文档/记忆（不同维度向量空间不同）。
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
    # 对话滚动摘要（长会话上下文压缩）：窗口外的旧对话由 LLM 滚动压缩成一段摘要，
    # 注入 system prompt（route 决策 + 最终生成），避免长会话「忘了开头说啥」。
    # 与 Mem0 长期记忆互补：Mem0 管「事实/偏好」，本机制管「对话流」；二者均异步后台跑。
    CONV_SUMMARY_ENABLED: bool = True       # 总开关：false 则纯固定窗口（旧消息直接丢弃）
    CONV_SUMMARY_KEEP_RECENT: int = 10     # 保留最近 N 条原始消息不摘要（细节不失真）
    CONV_SUMMARY_STEP: int = 6             # 窗口外每积累 N 条新消息才重新调 LLM 摘要一次（省成本）
    # 知识图谱 / Graph RAG（Phase 3 T1；Postgres 图存储，无需 Neo4j server）
    GRAPH_ENABLED: bool = True         # 总开关：false 则跳过建图与图检索，回退普通 RAG
    GRAPH_TOP_K: int = 5               # 每轮问答图检索召回的实体种子数（再去 1 跳扩展）
    GRAPH_MULTI_HOP_MAX: int = 2       # 8.5 图谱多跳推理最大跳数（complex 意图触发）
    GRAPH_MULTI_HOP_TOP_CHAINS: int = 8  # 8.5 多跳推理返回的最多链路条数
    # Reranker（8.2）：RRF 融合后的精细重排层
    RERANKER_ENABLED: bool = True      # 总开关：false 则跳过重排，直接返回 RRF 结果
    RERANKER_METHOD: str = "auto"      # auto(优先 cross-encoder，否则规则) | cross-encoder | lexical-semantic
    # 意图分类（8.3）：LLM 判断 simple/complex/greeting/web_search，complex 触发图谱多跳
    INTENT_ENABLED: bool = True        # 总开关：false 则退化为正则启发式（greeting/web）
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
    # admin 默认档案字段（首次自动创建时写入；已存在则补全空缺项）
    ADMIN_EMAIL: str = "admin@knoa.local"
    ADMIN_DEPARTMENT: str = "总部"
    ADMIN_EMPLOYEE_ID: str = "A0001"
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
    # 阿里云 OSS（前端直传 + 服务端 PostObject 签名，零 SDK）。
    # 服务端用 AccessKeySecret 算签名给前端，前端直接 POST 到 OSS，后端只存可访问 URL。
    # bucket 建议设为公共读（public-read），这样后端摄入回抓字节、大模型读取图片附件都能直接访问；
    # 若为私有桶则需对读取方下发签名 URL（本实现暂按公共读设计）。
    OSS_ENABLED: bool = False           # 显式 True 才启用 OSS 直传（否则前端回退 base64 旧流程）
    OSS_BUCKET: str = ""
    OSS_ENDPOINT: str = ""              # 形如 oss-cn-hangzhou.aliyuncs.com（不含 https://）
    OSS_REGION: str = ""                # 形如 cn-hangzhou
    OSS_ACCESS_KEY_ID: str = ""
    OSS_ACCESS_KEY_SECRET: str = ""
    OSS_UPLOAD_PREFIX: str = "uploads"  # 对象 key 前缀（区分文档/对话：uploads/docs、uploads/chat）
    OSS_MAX_SIZE: int = 100 * 1024 * 1024  # 单文件上限 100MB
    # App
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"
    # CORS：携带凭据（HttpOnly Cookie）时必须显式指定源，不能用 "*"
    CORS_ALLOW_CREDENTIALS: bool = True
    # 鉴权 Cookie（P1-8：token 改 HttpOnly Cookie，防 XSS 窃取）
    COOKIE_NAME: str = "knoa_token"
    # ponytail: dev(http) 自动关闭 Secure，使 HttpOnly Cookie 能被浏览器存储；生产(https)仍为 True
    COOKIE_SECURE: bool = APP_ENV != "development"
    COOKIE_SAMESITE: str = "lax"
    # 腾讯云 TTS（语音播报；httpx 直连 + 手写 TC3 签名，不引第三方 SDK）
    # 留空则 /api/tts 优雅降级返回 503，前端朗读按钮自动隐藏
    TENCENT_TTS_SECRET_ID: str = ""
    TENCENT_TTS_SECRET_KEY: str = ""
    TENCENT_TTS_REGION: str = "ap-guangzhou"
    TTS_VOICE_TYPE: int = 1004       # 1002 成熟男声 | 1004 温润女声 | 1050 新闻女声
    TTS_CODEC: str = "mp3"           # mp3 便于长文本分块拼接（帧级可追加）
    TTS_SAMPLE_RATE: int = 16000
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# 已知 OpenAI 兼容 embedding 模型 → 标准向量维度。
# 用于生产启动期维度一致性校验（避免 EMBEDDING_DIM 与模型实际维度错配
# 导致 pgvector 检索因维度不符全过滤空、直接失效）。
_KNOWN_EMBEDDING_DIMS: dict[str, int] = {
    # text-embedding-v4（阿里云百炼 Qwen3-Embedding）维度可配，1024 为默认值；
    # 若改用 1536/2048 等，须同步把这里改为对应值，否则生产校验会因维度不符拦截启动。
    "text-embedding-v4": 1024,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def validate_production_settings() -> None:
    """生产环境启动期强校验：发现仍在使用弱默认值/危险配置即直接抛异常阻止启动。

    把「配置没改就上线」这类高危问题从「运行时悄悄出错」变成「启动即失败」，
    避免带着 dev 密钥 / 弱口令 / 维度错配上线。仅在生产环境
    （APP_ENV=production）生效，开发环境（默认 development）不干预，方便本地调试。
    """
    if settings.APP_ENV != "production":
        return
    errors: list[str] = []
    if settings.JWT_SECRET == "dev-change-me":
        errors.append(
            "JWT_SECRET 仍为开发默认值 'dev-change-me'，生产环境必须替换为强随机密钥"
        )
    if settings.ADMIN_PASSWORD == "admin123":
        errors.append(
            "ADMIN_PASSWORD 仍为弱口令 'admin123'，生产环境必须替换为强密码"
        )
    if settings.EMBEDDING_API_KEY == "":
        errors.append("EMBEDDING_API_KEY 为空，生产环境无法向量化，检索将全部失效")
    if settings.LLM_API_KEY == "":
        errors.append("LLM_API_KEY 为空，生产环境无法调用大模型")
    expected = _KNOWN_EMBEDDING_DIMS.get(settings.EMBEDDING_MODEL)
    if expected is not None and settings.EMBEDDING_DIM != expected:
        errors.append(
            f"EMBEDDING_DIM={settings.EMBEDDING_DIM} 与模型 "
            f"{settings.EMBEDDING_MODEL} 的标准维度 {expected} 不一致，"
            "将导致向量维度错配、检索全空"
        )
    # 仅当数据库指向非本地主机（真实远程生产库）且仍用默认弱口令时才拦截；
    # localhost / 容器服务名（postgres）等本地或编排场景放宽，避免误伤开发启动。
    from urllib.parse import urlparse

    _db_host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    if "knoa:knoa@" in settings.DATABASE_URL and _db_host not in (
        "localhost", "127.0.0.1", "postgres", ""
    ):
        errors.append(
            "DATABASE_URL 仍使用默认弱口令 'knoa:knoa' 且指向远程主机，"
            "生产环境必须设置强密码"
        )
    if errors:
        raise RuntimeError(
            "生产环境配置校验未通过，已阻止启动：\n- " + "\n- ".join(errors)
        )


settings = Settings()
