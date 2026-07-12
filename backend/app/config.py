from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://knoa:knoa@localhost:5432/knoa"
    REDIS_URL: str = "redis://localhost:6379/0"
    # Embedding (OpenAI-compatible API)
    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    # LLM (M3 启用)
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2000
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
    RRF_K: int = 60
    # Elasticsearch (Phase 2 混合检索；venv 装不了官方客户端，走 httpx 直连 REST)
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
    # App
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
