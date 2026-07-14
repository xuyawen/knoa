# 知海 Knoa · 跨境运营 AI 知识库

面向电商平台卖家的 RAG 问答系统：基于自有知识库做检索增强生成，答案带**溯源引用**，支持多会话历史、答案反馈、知识库浏览与文档管理。适用于亚马逊、eBay、Shopify、TikTok Shop 等主流平台的运营知识管理场景。产品定位见 `docs/design-spec.md`。

## 技术栈

- **前端**：Vue 3 + Vite + TypeScript + vue-router + Pinia
- **后端**：FastAPI + SQLAlchemy(async) + Redis（向量存储用 JSONB + numpy 余弦，不引 pgvector / langchain）
- **检索**：混合检索（BM25 关键词 + 向量稠密检索），RRF 融合重排
- **生成**：OpenAI 兼容接口的大模型（LLM、Embedding 均通过 `.env` 配置，可切换 DeepSeek / OpenAI / 通义 / 自建等）
- **基础设施**：PostgreSQL 16 + Redis 7，均跑在 Docker 里（向量存于 JSONB，不依赖 pgvector 扩展）

## 系统架构

```
┌─────────────┐     /api (SSE)      ┌──────────────────────────────┐
│  Vue 3 前端 │ ───────────────────▶│  FastAPI 后端                │
│  HTTPS:5174 │◀───────────────────│  HTTPS:8000                  │
└─────────────┘     SSE 事件流       │  ├─ /api/ask   流式问答       │
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
- `embeddings.py` —— 调用 Embedding API 生成向量（默认 1536 维，以 `.env` 中 `EMBEDDING_DIM` 为准）
- `ingestor.py` —— 入库：写 `document` + `doc_chunk`（带向量）
- `retriever.py` —— 混合检索（BM25 + 向量），RRF 融合，取 top-k
- `agent.py` —— Agentic 决策：LLM 判断 `retrieve` / `supplement_search` / `direct_answer`；打招呼与闲聊跳过检索
- `pipeline.py` —— 问答主流程：检索 → 流式生成 → 注入引用 → 心跳/超时保护

> 详细文档见 [`docs/architecture.md`](./docs/architecture.md)（架构图 + 技术决策）、[`docs/api.md`](./docs/api.md)（API 参考）、[`docs/runbook.md`](./docs/runbook.md)（运维手册）；部署细节见 `deploy/nginx/README.md`。

## 目录结构

```
knoa/
├── docker-compose.yml          # 全栈编排：Postgres + Redis + backend + frontend（Phase 4）
├── docs/design-spec.md        # 设计规格（配色 / 字体 / 布局 / 接口）
├── handoff/                   # 设计稿导出与解析脚本
├── backend/                   # FastAPI 后端
│   ├── Dockerfile             # 后端镜像（python:3.12-slim）
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

需要本地跑两个中间件，已在根目录 `docker-compose.yml`（仅 infra）配好：

```bash
# 仅起 Postgres(5433) 与 Redis(6380)，便于本机直接跑 uvicorn 开发
docker compose up -d postgres redis
```

依赖版本：PostgreSQL 16、Redis 7。（向量存于 JSONB，不依赖 pgvector 扩展。）

### 全栈 Docker 部署（Phase 4）

```bash
# 生产（推荐）：edge 反代 TLS 终止 + 每日 PG 备份；
#   postgres/redis/backend/frontend 仅容器网络内，只有 edge 暴露 80/443
docker compose up -d --build
# 访问：https://localhost （edge 把 /api/ 反代到 backend:8000，/ 反代到 frontend:80）
# 健康检查：curl -kI https://localhost/api/health

# 本地开发：恢复宿主机端口（5433/6380/8080）并关闭 edge/backup
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

- 仅 `edge` 对外暴露 80/443；postgres/redis/backend/frontend 不发布宿主机端口（见 `docker-compose.yml` 注释）。
- 首次启动 backend 自动执行 `init_db()`（`create_all` 兜底）+ Alembic 迁移建表；**改了 ORM 模型要 `alembic revision --autogenerate`**（见 `docs/runbook.md`）。
- 上传文件持久化在 `knoa_uploads` 卷；Postgres / Redis 数据分别在 `knoa_pgdata` / `knoa_redisdata` 卷；备份在 `knoa_backups` 卷。
- 生产 TLS 由 `edge`（nginx:alpine）终止，证书放宿主机 `deploy/nginx/certs/`，详见 `deploy/nginx/README.md`。

## 快速开始

### 1. 后端

```bash
cd backend

# 首次安装依赖（已锁定在 uv.lock）
uv sync                 # 或：uv pip install -e .

# 准备环境变量
cp .env.example .env   # 然后填入 LLM / Embedding 的 API Key

# 1. 生成本地自签证书（已生成则可跳过，证书文件在 backend/certs/，不进 git）
openssl req -x509 -newkey rsa:2048 -keyout backend/certs/key.pem \
  -out backend/certs/cert.pem -days 365 -nodes -subj "/CN=localhost"

# 2. 启动（用项目 venv 的 python，确保 uvicorn 可用）
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --ssl-keyfile ../certs/key.pem --ssl-certfile ../certs/cert.pem
```

> 启动后访问 `https://localhost:8000/api/health` 验证（浏览器会提示自签证书风险，点"继续访问"即可；`curl -k https://localhost:8000/api/health`）。
> 注意：uvicorn 无 `--reload`，改了 `.py` 需手动重启后端进程。

### 2. 前端

```bash
cd frontend
npm install
npm run dev            # 默认 https://localhost:5174
```

浏览器打开 `https://localhost:5174`，首次会提示自签证书风险，点击"继续访问"。
`vite.config.ts` 已将 `/api` 代理到 `https://localhost:8000`（并关闭了 SSE 响应的压缩以避免缓冲）。
若 5174 被占用，Vite 会自动顺延端口（如 5175），以终端输出为准。

> 安全说明：前后端均启用 HTTPS/TLS，登录密码在传输过程中由 TLS 1.3 AES-GCM 加密。
> 浏览器 DevTools 的 **Payload 面板显示的是 TLS 解密后的明文**，这是调试视图，不代表网络线上可被截获。

## 配置

后端所有配置通过 `backend/.env` 驱动，范本见 `.env.example`：

| 配置项 | 说明 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 连接串（asyncpg），默认 `postgresql+asyncpg://knoa:knoa@localhost:5433/knoa` |
| `REDIS_URL` | Redis 连接串，默认 `redis://localhost:6380/0` |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 大模型（OpenAI 兼容接口） |
| `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` | 向量模型（OpenAI 兼容接口，可与 LLM 不同厂商） |
| `RAG_TOP_K` / `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` / `RAG_CHUNK_MIN_CHARS` / `RRF_K` | 检索与切分参数（`RAG_CHUNK_MIN_CHARS` 为短文本噪声地板，低于此且无实质字符的内容视为噪声丢弃，但整篇有内容时保底至少 1 块） |
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

**Phase 1 — 核心问答（✅ 完成）**
- [x] 前端骨架 + 亮/暗/系统主题切换
- [x] 桌面主工作台 + 移动端工作台
- [x] 后端 RAG 管线（混合检索 BM25+向量 + RRF + Agentic 决策 + SSE 流式问答）
- [x] 知识库浏览 + 文档上传（JSON 文本方式，避开 multipart 依赖）
- [x] 答案溯源详情接口与前端抽屉
- [x] 多会话历史（列表 / 新建 / 切换 / 持久化）
- [x] 反馈闭环（点赞 / 点踩 / 复制）
- [x] 种子语料入库（5 库 / 63 篇真实文档）
- [x] 高频问题统计（闲聊过滤）

**Phase 2 — 企业级增强（✅ 完成）**
- [x] RBAC 鉴权（admin/editor/viewer + 库级权限，手写 JWT，无 PyJWT 依赖）
- [x] ES 混合检索（kNN + BM25 + RRF，IK 中文分词；不可达自动回退 pgvector）
- [x] Mem0 长期记忆（自研轻量版，JSONB+numpy 余弦，零新依赖）

**Phase 3 — AI 能力扩展（✅ 完成）**
- [x] 知识图谱 Graph RAG（Postgres 存图，摄入抽实体/关系，检索向量+1跳）
- [x] LangGraph 风格 Agent（纯 stdlib 节点图状态机，行为不变）
- [x] 文档解析管线 + 对象存储（md/txt/docx/pdf；local + S3 SigV4 零 SDK）

**Phase 4 — 工程化（✅ 完成）**
- [x] Alembic 迁移脚手架 + 初始迁移
- [x] Docker 容器化 + compose 编排
- [x] CI/CD（前端类型检查+构建 / 后端编译+迁移契约 / pytest 7 passed）
- [x] 生产部署加固（edge TLS 反代 + PG 每日备份 + compose prod profile）
- [x] 架构与运维文档（docs/architecture.md · api.md · runbook.md）

> 详细文档见 [`docs/architecture.md`](./docs/architecture.md)（架构图）、[`docs/api.md`](./docs/api.md)（API 参考）、[`docs/runbook.md`](./docs/runbook.md)（运维手册）；部署细节见 `deploy/nginx/README.md`。
