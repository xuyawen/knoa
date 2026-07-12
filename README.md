# 知海 Knoa · 跨境运营 AI 知识库

面向亚马逊美国站卖家的 RAG 问答系统：基于自有知识库做检索增强生成，答案带**溯源引用**，支持多会话历史、答案反馈、知识库浏览与文档管理。产品定位见 `docs/design-spec.md`。

## 技术栈

- **前端**：Vue 3 + Vite + TypeScript + vue-router + Pinia
- **后端**：FastAPI + SQLAlchemy(async) + pgvector + Redis
- **检索**：混合检索（BM25 关键词 + 向量稠密检索），RRF 融合重排
- **生成**：OpenAI 兼容接口的大模型（LLM、Embedding 均通过 `.env` 配置，可切换 DeepSeek / OpenAI / 通义 / 自建等）
- **基础设施**：PostgreSQL 16（含 pgvector 扩展）+ Redis 7，均跑在 Docker 里

## 系统架构

```
┌─────────────┐     /api (SSE)      ┌──────────────────────────────┐
│  Vue 3 前端 │ ───────────────────▶│  FastAPI 后端                │
│  (5173)     │◀───────────────────│  ├─ /api/ask   流式问答       │
└─────────────┘     SSE 事件流       │  ├─ /api/knowledge-bases 库/文档│
       │                              │  ├─ /api/sources 溯源详情     │
       │ Pinia 状态                  │  ├─ /api/sessions 多会话历史  │
       ▼                              │  ├─ /api/feedback 反馈        │
  Workbench / Mobile                │  └─ /api/trending 高频问题     │
                                    └───────┬───────────┬──────────┘
                                            │           │
                                    ┌───────▼───┐ ┌─────▼─────┐
                                    │ PostgreSQL │ │  Redis    │
                                    │ +pgvector  │ │ 趋势计数   │
                                    └───────────┘ └───────────┘
```

后端 RAG 管线（`app/core/rag/`）：

- `chunker.py` —— 文档按固定窗口切分（默认 500 字 / 重叠 50）
- `embeddings.py` —— 调用 Embedding API 生成向量（默认 1024 维）
- `ingestor.py` —— 入库：写 `document` + `doc_chunk`（带向量）
- `retriever.py` —— 混合检索（BM25 + 向量），RRF 融合，取 top-k
- `agent.py` —— Agentic 决策：LLM 判断 `retrieve` / `supplement_search` / `direct_answer`；打招呼与闲聊跳过检索
- `pipeline.py` —— 问答主流程：检索 → 流式生成 → 注入引用 → 心跳/超时保护

## 目录结构

```
knoa/
├── docs/design-spec.md        # 设计规格（配色 / 字体 / 布局 / 接口）
├── handoff/                   # 设计稿导出与解析脚本
├── backend/                   # FastAPI 后端
│   ├── docker-compose.yml     # Postgres(5433) + Redis(6380)
│   ├── pyproject.toml        # 依赖锁定（uv.lock）
│   ├── app/
│   │   ├── main.py            # 应用入口，挂载所有 /api 路由
│   │   ├── config.py          # 配置（读 .env）
│   │   ├── database.py        # async SQLAlchemy 引擎 / session
│   │   ├── db/               # ORM 模型（KnowledgeBase/Document/DocChunk/ChatSession/...）
│   │   ├── models/           # Pydantic 请求/响应模型
│   │   ├── routers/          # 路由：ask/knowledge/sources/sessions/feedback/trending/health
│   │   ├── core/
│   │   │   ├── llm/          # LLM 兼容封装（openai_compat）
│   │   │   ├── rag/          # 检索增强管线（见上）
│   │   │   └── store/        # Redis 封装（趋势计数等）
│   │   ├── data/
│   │   │   ├── seed.py       # 初始化知识库元数据 + 高频问题（幂等）
│   │   │   ├── ingest_seed.py# 扫描 markdown 目录并向量化入库
│   │   │   └── markdown/     # 种子语料（5 个知识库的真实运营文档）
│   │   └── deps.py           # 依赖注入（redis 等）
│   └── tests/
└── frontend/                  # Vue 3 前端
    └── src/
        ├── views/
        │   ├── Workbench.vue          # 桌面主工作台（三栏：侧栏/对话/溯源）
        │   ├── MobileWorkbench.vue    # 移动端工作台
        │   ├── KnowledgeBases.vue     # 知识库列表
        │   └── KnowledgeBaseDetail.vue# 知识库详情 + 文档列表 + 上传
        ├── components/
        │   ├── AppSidebar.vue / MobileNav.vue / TopBar.vue
        │   ├── ChatStream.vue / MessageBubble.vue / Composer.vue
        │   ├── SourcePanel.vue / SourceCard.vue / SourceDetailDrawer.vue
        │   ├── CitationChip.vue / FeedbackBar.vue
        │   ├── HistoryDrawer.vue       # 多会话历史（切换/新建）
        │   ├── KnowledgeCard.vue / TrendingList.vue / HealthBar.vue
        │   ├── ThemeToggle.vue / Icon.vue
        │   ├── composables/useTheme.ts # 亮/暗/跟随系统，持久化 localStorage
        │   ├── stores/                 # pinia：chat.ts / knowledge.ts
        │   ├── api/index.ts            # 接口封装
        │   ├── types/api.ts            # 类型定义
        │   ├── router/index.ts         # 路由（含 /knowledge-bases、/:id）
        │   └── style.css               # 设计 Token（CSS 变量，亮/暗双主题）
```

## 环境依赖

需要本地跑两个中间件，已在 `backend/docker-compose.yml` 配好：

```bash
cd backend
docker compose up -d     # 启动 Postgres(5433) 与 Redis(6380)
```

依赖版本：PostgreSQL 16（开启 `pgvector`）、Redis 7。

## 快速开始

### 1. 后端

```bash
cd backend

# 首次安装依赖（已锁定在 uv.lock）
uv sync                 # 或：uv pip install -e .

# 准备环境变量
cp .env.example .env   # 然后填入 LLM / Embedding 的 API Key

# 启动（用项目 venv 的 python，确保 uvicorn 可用）
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> 启动后访问 `http://localhost:8000/api/health` 验证（`{"status":"ok"}`）。
> 注意：uvicorn 无 `--reload`，改了 `.py` 需手动重启后端进程。

### 2. 前端

```bash
cd frontend
npm install
npm run dev            # 默认 http://localhost:5173
```

`vite.config.ts` 已将 `/api` 代理到 `http://localhost:8000`（并关闭了 SSE 响应的压缩以避免缓冲）。
若 5173 被占用，Vite 会自动顺延端口（如 5174），以终端输出为准。

## 配置

后端所有配置通过 `backend/.env` 驱动，范本见 `.env.example`：

| 配置项 | 说明 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 连接串（asyncpg），默认 `postgresql+asyncpg://knoa:knoa@localhost:5433/knoa` |
| `REDIS_URL` | Redis 连接串，默认 `redis://localhost:6380/0` |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 大模型（OpenAI 兼容接口） |
| `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` | 向量模型（OpenAI 兼容接口，可与 LLM 不同厂商） |
| `RAG_TOP_K` / `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` / `RRF_K` | 检索与切分参数 |
| `CORS_ORIGINS` | 允许的前端来源 |
| `LANGSMITH_TRACING` | 可选，开启 LLM 调用追踪 |

## 数据初始化

知识库语料放在 `backend/app/data/markdown/{kb_id}/`，目前为 **5 个知识库 / 63 篇真实亚马逊美国站运营文档**（合规、广告、物流、选品、客服），内容基于真实政策与运营常识，不虚构。

```bash
cd backend

# 1) 初始化知识库元数据 + 高频问题（幂等，重复执行安全）
.venv/Scripts/python.exe -m app.data.seed

# 2) 向量化入库：扫描 markdown 目录 → 调 Embedding → 写 document/doc_chunk
.venv/Scripts/python.exe -m app.data.ingest_seed
```

已入库后，`/api/knowledge-bases` 会返回各库文档数，问答即可基于真实语料检索。

## API 概览

所有接口前缀 `/api`：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| POST | `/ask` | 问答（SSE 流式：`sources` → `delta` → `done`） |
| GET | `/knowledge-bases` | 知识库列表（含健康度/文档数） |
| GET | `/knowledge-bases/{kb_id}/documents` | 某库文档列表 |
| POST | `/knowledge-bases/{kb_id}/documents` | 上传文档（JSON `{filename, content}`，非 multipart） |
| GET | `/sources/{chunk_id}` | 溯源详情（片段原文 + 出处） |
| GET | `/sessions` | 会话列表 |
| POST | `/sessions` | 新建会话 |
| GET | `/sessions/{session_id}` | 会话详情（含全部消息与引用） |
| POST | `/feedback` | 答案反馈（点赞/点踩/复制） |
| DELETE | `/feedback/{message_id}` | 撤销反馈 |
| GET | `/trending` | 高频问题排行（闲聊已过滤） |

> `/api/ask` 的 SSE 事件以 CRLF 分隔，前端需按 `\r\n` 切分。

## 功能与页面

- **桌面工作台（Workbench）**：左侧知识库/会话导航，中间对话流，右侧溯源面板（引用可点开看原文）。
- **移动端（MobileWorkbench）**：底部导航，亮/暗适配。
- **知识库浏览**：列表页查看各库健康度；详情页查看文档、支持上传新文档。
- **多会话历史**：侧栏/抽屉切换历史会话、新建对话，会话可持久化续聊。
- **答案溯源**：每条回答内联引用角标 `[1][2]`，点开抽屉查看命中片段与出处文档。
- **反馈闭环**：对每条回答点赞 / 点踩 / 复制。
- **高频问题**：首页展示真实业务高频提问（已剔除打招呼/闲聊）。
- **主题**：亮 / 暗 / 跟随系统，统一由 `style.css` 的 CSS 变量控制。

## 进度

- [x] 设计规格文档（design-spec.md）
- [x] 前端骨架 + 亮/暗/系统主题切换
- [x] 桌面主工作台 + 移动端工作台
- [x] 后端 RAG 管线（混合检索 + Agentic 决策 + SSE 流式问答）
- [x] 知识库浏览 + 文档上传（JSON 文本方式，避开 multipart 依赖）
- [x] 答案溯源详情接口与前端抽屉
- [x] 多会话历史（列表 / 新建 / 切换 / 持久化）
- [x] 反馈闭环（点赞 / 点踩 / 复制）
- [x] 种子语料入库（5 库 / 63 篇真实文档 / 419 切片）
- [x] 高频问题统计（闲聊过滤）

## 后续路线（Phase 2–4）

- **Phase 2**：ES 混合检索增强、RBAC 权限、Mem0 长期记忆
- **Phase 3**：Neo4j 知识图谱、LangGraph Agent、MinIO 文件存储与解析管线（PDF/DOCX）
- **Phase 4**：Alembic 迁移、Docker 化部署、CI/CD
