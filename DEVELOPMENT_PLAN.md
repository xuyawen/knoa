# Knoa 分阶段开发计划（对照 12 张原型图）

> 目标：把系统从「UI 骨架 60~70% / 数据真实性 30% / AI 能力 20%」补齐到原型设计的功能完备度。
> 基线：前端 `frontend/src/views/*`（Dashboard/Documents/Search/Chat/Graph/Permission/Profile），后端 `backend/app/{routers,core,models,db}`。
> 约束：CI 要求前端 `npm run build`（含 `vue-tsc` 类型检查）零错；后端改动走 Alembic 迁移；`.env`/密钥不进 git；面试类 md 不进 git。

---

## 0. 现状缺口速览（来自逐图对照）

| 原型 | 页面 | 现状 | 主要缺口 |
|---|---|---|---|
| #1 | 总览/价值主张 | 无 | 系统外介绍页，不做成交互 |
| #2 | Dashboard | 部分 | 指标卡后3项硬编码、趋势图随机、5 个分区 4 个 ComingSoon、操作记录 5 行硬编码 |
| #3 | 文档管理 | 部分 | 上传人/权限范围假、解析状态未渲染、分页未接服务端 total |
| #5 | AI 问答 | 较完整 | 引用卡片字段略差异，其余对齐 |
| #6 | 知识图谱 | 部分 | 筛选下拉未联动、导出无事件、Top5/最近更新缺 |
| #7 | 核心功能架构 | 示意 | 语义检索缺 Reranker、KG 构建流水线未做 |
| #8 | 多模态支持 | 缺失 | 音频/视频/OCR/跨模态检索均无 |
| #9 | 技术架构全景 | 部分 | 缺 Elasticsearch/Neo4j/Reranker/TTS/LangFuse（目前 BM25+PG 兜底、stdlib 状态机） |
| #10 | 数据架构 | 部分 | 缺 ES 索引层、Neo4j 图层（PG 兜底） |
| #11 | 文档处理管线 | 部分 | 异步任务表有，前端未轮询进度 |
| #12 | Agent 决策流程 | 部分 | 缺 Reranker/图谱多跳/意图分类/LangFuse tracing |

**根因定位**
- 数据造假：后端无业务统计接口（analytics/operations/announcements），前端被迫硬编码/随机。
- 文档字段缺：`Document` 模型无 `uploader_id/scope/parse_status`，所以上传人/权限范围只能造假。
- AI 半成品：Reranker、意图分类、KG 回填、图谱推理均未实现，Agent 仅混合检索+记忆。

---

## 1. 阶段划分总览

| Phase | 目标 | 关键产出 | 预估工时 | 前置依赖 |
|---|---|---|---|---|
| P0 | 数据模型地基 | Document 补全字段 + 迁移 + 回填 | 1 天 | 无 |
| P1 | 业务统计后端 | analytics/operations/announcements 三套接口 | 1.5 天 | P0 |
| P2 | Dashboard 全分区真实化 | 6 分区接真数据 | 1 天 | P1 |
| P3 | 文档管理真实化 | 上传人/权限范围/解析状态/服务端分页 | 1 天 | P0 |
| P4 | 图谱周边补全 | 筛选联动/导出/Top5/最近更新 | 1 天 | 无（独立） |
| P5 | 部门树/标签/上传进度 | 3 个交互模块 | 1.5 天 | P0 |
| P6 | AI 能力增强 | Reranker/意图分类/KG回填/图谱推理 | 3 天 | P0,P4 |
| P7 | 多模态扩展 | 音频/视频/OCR/跨模态检索 | 3 天 | P0 |
| P8 | 可观测与收尾 | 通知中心/系统设置/TTS/LangFuse | 2 天 | P1,P6 |

> 优先级建议：P0→P1→P2→P3 先解决「数据真实性」（最易被面试抓包）；P4/P5 提升完成度；P6/P7 是 AI 亮点；P8 收尾。

---

## 2. Phase 0 — 数据模型地基

### 2.1 目标
让文档具备真实「上传人 / 权限范围 / 解析状态」三要素，为后续所有真实化打底。

### 2.2 后端任务
**文件：`backend/app/models/knowledge.py`**
- `Document` ORM 类新增列：
  - `uploader_id: Mapped[str|None]`（FK→user.id，允许历史数据空）
  - `uploader_name: Mapped[str|None]`（冗余显示名，避免每次 join）
  - `scope: Mapped[str]` 默认 `'public'`，枚举 `['private','department','company','public']`（对应原型「仅本人/部门/公司/公开」）
  - `parse_status: Mapped[str]` 默认 `'pending'`，枚举 `['pending','parsing','done','failed']`
- `DocumentOut` pydantic 补 `uploaderName`/`scope`/`parseStatus` 字段。

**文件：`backend/app/db/init_db.py`**
- 加幂等 ALTER（`ADD COLUMN IF NOT EXISTS`），与现有 `_migrate_columns` 一致。
- 写一次性回填脚本（幂等，跑完即删或置 `--backfill` 开关）：
  - `uploader_name` 取创建者或默认 `'系统'`；
  - `scope` 默认 `'public'`；
  - `parse_status` 由关联 `DocumentTask.status` 映射（completed→done，failed→failed，其余 pending）。

**文件：`backend/app/alembic/`**
- `uv run alembic revision --autogenerate -m "add document uploader scope parse_status"` → `uv run alembic upgrade head` 本地验证。
- 注：CI 会跑 `alembic upgrade head`，迁移必须可重复执行（无破坏式 DROP）。

**文件：`backend/app/routers/knowledge.py`**
- `DocumentUploadIn` 加 `scope` 字段（默认 public）；上传时写入 `uploader_id=current_user.id`、`uploader_name=current_user.display_name`、`scope`、`parse_status='pending'`。
- `get_documents` 列表查询按 `scope` + 当前用户部门做可见性过滤（private 仅本人，department 仅同部门，company/public 登录可见）。
- 审核通过（approve）时把 `parse_status` 置 `'done'`（与 DocumentTask 状态同步）。

### 2.3 前端任务
- 暂不改视图（P3 统一改），但 `src/types/api.ts` 的 `DocumentItem` 需补 `uploaderName`/`scope`/`parseStatus` 类型（P3 用）。

### 2.4 验收
```bash
# 本地起后端（关 SSL 便于 curl）
cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 &
curl -k -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8001/api/knowledge-bases/<kb>/documents | python -m json.tool
# 确认返回含 uploaderName / scope / parseStatus 字段且非假值
```

---

## 3. Phase 1 — 业务统计后端

### 3.1 目标
补齐 Dashboard 所需的全部业务统计接口，消灭硬编码与随机数据。

### 3.2 后端任务

**新建 `backend/app/models/operation_log.py`**
- `OperationLog` 表：`id`/`user_id`/`display_name`/`action`(upload|update|delete|login|ask|download|approve|reject)/`related_doc_id`(可空)/`detail`(可空)/`created_at`(默认 now())。
- `OperationLogOut` pydantic（camelCase）。

**新建 `backend/app/models/announcement.py`**
- `Announcement` 表：`id`/`title`/`content`/`level`(info|warn|critical)/`pinned`(bool)/`created_at`。
- `AnnouncementOut` pydantic。

**新建 `backend/app/routers/analytics.py`**（注册到 `main.py`）
- `GET /api/analytics/dashboard`
  返回 `{ totalDocs, todayNewDocs, aiAnswers, userSearches, activeUsers, deltas:{...} }`。
  聚合来源：
  - `totalDocs` = `select count(Document)`；
  - `todayNewDocs` = 今日 `created_at`；
  - `aiAnswers` = `OperationLog.action='ask'` 当日计数；
  - `userSearches` = `OperationLog.action='download' or 'search'` 或独立埋点；
  - `activeUsers` = 当日有 `OperationLog` 的去重 `user_id` 数；
  - `deltas` = 与昨日同口径差值（百分比）。
- `GET /api/analytics/trend?range=today|week|month`
  返回 `{ points:[{date, aiAnswers, searches}], labels:[...] }`，按日聚合 `OperationLog`。
- `GET /api/analytics/doc-category`
  复用现有 KB 统计逻辑（按 `category` 分组 count），返回饼图数据。

**新建 `backend/app/routers/operations.py`**
- `GET /api/operations?page=1&size=10` → `{ items:OperationLogOut[], total, page, size }`，按 `created_at` 倒序。
- 落日志点（在对应 router 内调用，best-effort）：
  - `auth.py` 登录成功 → `login`
  - `knowledge.py` 上传/审核通过/驳回/删除 → `upload`/`approve`/`reject`/`delete`
  - `ask.py` 问答完成 → `ask`（带 session_id）
  - `sessions.py` 下载/导出 → `download`

**新建 `backend/app/routers/announcements.py`**
- `GET /api/announcements` → `list[AnnouncementOut]`（pinned 优先，按 `created_at` 倒序）。
- `POST/PUT/DELETE /api/announcements`（admin 写，登录可读）—— 供 Phase 8 系统设置用。

**迁移**：`OperationLog`/`Announcement` 走 Alembic autogenerate + `upgrade head`。

### 3.3 前端任务
- `src/api/index.ts` 新增：
  - `getDashboardMetrics()` → `/api/analytics/dashboard`
  - `getTrend(range)` → `/api/analytics/trend?range=`
  - `getDocCategory()` → `/api/analytics/doc-category`
  - `getOperations(page,size)` → `/api/operations`
  - `getAnnouncements()` → `/api/announcements`
- `src/types/api.ts` 补对应返回类型。

### 3.4 验收
```bash
curl .../api/analytics/dashboard        # 返回真实计数+delta
curl .../api/operations?page=1&size=10  # 返回真实流水+total
curl .../api/announcements              # 返回公告列表
```

---

## 4. Phase 2 — Dashboard 全分区真实化

### 4.1 目标
6 个分区全部接真数据，消灭 `genTrendPoints` 随机与 5 行硬编码。

### 4.2 前端任务（文件 `frontend/src/views/Dashboard.vue`）
- **指标卡**：`onMounted` 调 `getDashboardMetrics()`，5 卡填真实值 + delta 涨跌箭头（绿涨红跌，遵循中文习惯）。
- **趋势图**：`trendRange` 切换 today/week/month → 调 `getTrend(range)`，SVG 折线用真实 `points`。
- **饼图**：`getDocCategory()` 真实占比（原 `pieData` 已有，换数据源）。
- **操作记录**：`getOperations()` 真实分页（替换 `activityLog` 硬编码 5 行），表格列对齐原型（操作时间/操作用户/操作类型/操作内容/相关文档链接）。
- **5 个 ComingSoon 分区实现**：
  - 访问分析 → 复用趋势图 + 访问量明细表（来自 `/api/analytics/trend`）
  - 文档统计 → 按 category/status 聚合（来自 dashboard 扩展或新增 `/api/analytics/doc-stats`）
  - 用户统计 → 活跃用户/新增用户时序（来自 analytics，可复用 trend 思路）
  - 热门内容 → 复用现有 `getTrending()`（Search popular 已接）
  - 系统公告 → `getAnnouncements()` 列表渲染

### 4.3 验收
- `npm run build` 零类型错误。
- 浏览器逐一打开 6 个分区，数据均来自接口（Network 面板确认无 mock 常量）。

---

## 5. Phase 3 — 文档管理真实化

### 5.1 目标
上传人/权限范围/解析状态三列真实，分页接服务端 total。

### 5.2 后端任务（`backend/app/routers/knowledge.py`）
- `get_documents` 加查询参数 `?page=&size=&scope=&tag=`，返回 `{ items, total, page, size }`（目前返回裸 list，需改响应模型 `DocumentListOut`）。
- 列表项带 `uploader_name`/`scope`/`parse_status`（P0 已加字段）。
- 解析状态与 `DocumentTask` 实时同步（列表查询时 join task 取最新 status）。

### 5.3 前端任务（`frontend/src/views/Documents.vue`）
- 表格「上传人」列改 `doc.uploaderName`（删 `auth.user?.displayName` 假值）。
- 「权限范围」列改 `doc.scope` 映射中文标签（仅本人/部门/公司/公开），用真实 `.scope-tag`。
- 「解析状态」列新增 `.status-tag`（解析完成/解析中/解析失败）映射 `doc.parseStatus`。
- 底部分页接 `total` + 跳转，调 `getDocuments(kbId, {page,size})`。
- `filterScope` CustomSelect 改为真实过滤（传 `?scope=` 给后端，不再纯前端过滤）。
- 文件：`src/types/api.ts` 的 `DocumentItem` 补 `uploaderName`/`scope`/`parseStatus`。

### 5.4 验收
- 上传新文档后，列表「上传人」显示当前用户真名；「权限范围」随上传参数变化；「解析状态」随任务流转（pending→done）。
- 切到第 2 页发真实分页请求，total 正确。

---

## 6. Phase 4 — 图谱周边补全

### 6.1 目标
让 #6 图谱页从「引擎完整但周边残」变完整。

### 6.2 后端任务（`backend/app/routers/graph.py`）
- `GET /api/graph/hot-nodes?limit=5` → 热门知识点 Top5（按被引用次数/doc_chunk 关联度排序；先用节点度数近似）。
- `GET /api/graph/recent?limit=5` → 最近更新节点（按 `updated_at`）。
- `GET /api/graph/export?format=json|gexf` → 返回完整 `{nodes,edges}` 供前端下载。
- `GET /api/graph?node_type=&biz_category=&from=&to=` 已支持按参数过滤时，让查询真正生效（确认现有 `get_graph` 是否消费这些参数，未消费则补）。

### 6.3 前端任务（`frontend/src/views/Graph.vue`）
- 顶部搜索栏 3 个筛选（节点类型/业务分类/创建时间）绑定 `getGraph` 查询参数，变化时重新拉图（力导向重算）。
- 「导出图谱」按钮绑 `/api/graph/export`，用 `Blob` 触发下载 `.json`。
- 右侧「热门知识点 Top5」「最近更新节点」接新接口渲染。
- `stats` 分区已有 6 格真实统计，保留。

### 6.4 验收
- 改筛选条件，图布节点集合变化（非仅 UI 声明）。
- 点导出下载到文件，内容含 nodes/edges。

---

## 7. Phase 5 — 部门树 / 标签管理 / 上传进度

### 7.1 目标
把已有后端能力（Department 树、tags、DocumentTask）在前端用起来。

### 7.2 部门树 UI
- 后端 `GET /api/departments` 已返回嵌套树。
- 前端新建 `components/DepartmentTree.vue`：递归渲染树 + 选中回调。
- `Documents.vue`「部门文档」子菜单接部门树筛选（传 `department_id` 给 `get_documents`）。
- `Profile.vue` 或用户管理可显示所属部门。

### 7.3 标签管理 UI
- `Document.tags` / `KnowledgeBase.tags` 后端已存。
- `Documents.vue` 筛选加「标签」CustomSelect（拉取已有 tag 枚举）。
- KB 设置页（Phase 8 系统设置）加 tag 编辑输入。

### 7.4 上传进度条
- 上传后拿到 `DocumentTask.id`，轮询 `GET /api/documents/tasks/{id}`（`DocumentTaskOut.progress` 已有）。
- `Documents.vue` 上传区显示进度条（pending→processing 0-100→done），完成后自动刷新列表 + 解析状态变 done。

### 7.5 验收
- 部门树可展开选择并过滤「部门文档」。
- 上传大文件时进度条从 0 走到 100，列表自动刷新。

---

## 8. Phase 6 — AI 能力增强

### 8.1 目标
把 #7/#9/#12 里的 Reranker、意图分类、KG 回填、图谱多跳推理落地。

### 8.2 Reranker（`backend/app/core/retriever.py`）
- 在 RRF 融合得分后加重排层：
  - 优先用轻量 cross-encoder（若环境可装，如 `sentence-transformers` 的 rerank；否则用 LLM 打分或规则分数重排占位，标注可换模型）。
  - 输出 Top-K 重排后的 chunks。
- 保持接口不变（HybridRetriever 返回结构稳定）。

### 8.3 意图分类（`backend/app/core/agent.py`）
- 替换现有正则 greeting 快路，加 LLM 级意图判断：`simple`（仅混合检索）/ `complex`（触发图谱多跳推理）。
- 返回决策供 `_n_route` 使用，复杂问题走图谱分支（见 8.5）。
- 保留问候/常识快路作为兜底。

### 8.4 KG 回填（`backend/app/routers/knowledge.py` approve 流程）
- 审核通过后，调 LLM 从文档抽取实体/关系，写入 `kg_node`/`kg_edge`（现有 PG 表）。
- 失败不影响主流程（best-effort + 后台 `asyncio.create_task`，独立 db session）。
- 让 Graph 页 `getGraph` 返回真实非空节点（目前可能空）。

### 8.5 图谱多跳推理（`backend/app/core/agent.py` + `core/graph.py`）
- 复杂问题：从 question 抽取实体 → 在 `kg_node/kg_edge` 做多跳关联（BFS/DFS 限定跳数）→ 取推理链路文本。
- 把链路拼进 final prompt 的 context（与检索 chunks 并列）。

### 8.6 验收
- 检索结果顺序经 Reranker 调整（可对比重排前后）。
- 问复杂业务问题（如「A 流程和 B 流程的关系」）触发图谱分支，回答引用图谱链路。
- Graph 节点数 > 0（KG 回填生效）。

---

## 9. Phase 7 — 多模态扩展

### 9.1 目标
实现 #8 多模态支持：音频/视频/OCR + 跨模态检索雏形。

### 9.2 后端任务
**文件：`backend/app/core/parsers/`**（新建，stdlib + 可选软依赖）
- `audio.py`：音频（mp3/wav/m4a）→ ASR（优先调 STT API；无 key 时软依赖 `whisper`/`faster-whisper`，再无则占位返回提示）→ 转录文本进 DocChunk。
- `video.py`：视频（mp4）→ 抽帧（可选）+ 音频 ASR + 画面理解（调多模态模型）→ 整合文本。
- `image_ocr.py`：图片 → OCR（软依赖 `pytesseract` 或调多模态模型视觉描述）→ 文本。
- 统一：解析产物都进 `DocChunk`（文本向量），图片同时存 `image_vector`（可选，先文本兜底）。

**文件：`backend/app/routers/knowledge.py`**
- `DocumentUploadIn` 支持音频/视频/图片类型，路由到对应 parser。
- 上传后 `parse_status` 走真实解析流程。

### 9.3 前端任务
- `Documents.vue` 上传组件 `accept` 扩展音频/视频/图片类型。
- `Chat.vue` 附件支持音频/视频（目前仅图片 base64），走 `files` 载荷。
- `src/types/api.ts` 文件类型枚举扩展。

### 9.4 验收
- 上传一个 mp3 → 解析成可检索文本 → 问答能引用该音频内容。
- 上传图片 → 触发 OCR/视觉描述 → 可检索。

---

## 10. Phase 8 — 可观测与收尾

### 10.1 通知中心
- 复用 `Announcement` 表 + 新增「已读」标记（可选 `user_announcement_read` 关联表）。
- 前端顶栏铃铛组件显示未读数（来自 `/api/announcements` + 已读状态）。

### 10.2 系统设置页
- 新建 `frontend/src/views/Settings.vue` + 路由 `settings`（profile 同级）。
- 模型配置：把 Chat `model` 从 localStorage 提升到后端用户配置（`User` 表加 `preferred_model`，或独立 `user_settings` 表），`/api/settings` 读写。
- KB 管理入口、公告管理入口（admin）聚合至此。

### 10.3 TTS 语音播报（低优先级，可选）
- Agent 回答完成可选生成语音（调 TTS API）→ WebSocket 推前端同步播放（参考 #9/#12）。
- 若无 TTS key，留 UI 开关 + 占位，不阻塞主流程。

### 10.4 LangFuse 级 tracing（可选增强）
- 在现有 `core/metrics.py` 基础上，给每次 `/api/ask` 贯穿 `trace_id`（request_id 已存在），记录：检索耗时、召回 chunks、LLM token、是否触发图谱。
- 输出到 `/api/metrics` 或独立 `/api/traces` 端点，供效果评估看板。

### 10.5 验收
- 设置页改模型配置并落库，重新问答生效。
- 通知中心有未读红点，点开标记已读。

---

## 11. 跨阶段工程规范

### 提交前检查（每个 Phase 必做）
1. 前端：`cd frontend && npm run build`（= `vue-tsc -b` + `vite build`）零错误再提交。
2. 后端：改 `.py` 后若加表/列，必须 `uv run alembic revision --autogenerate` + 本地 `upgrade head`；CI 会跑 `alembic upgrade head` + `pytest`。
3. 安全：`.env`/`.github_token`/密钥绝不 `git add`；依赖单一真相 `backend/pyproject.toml`+`uv.lock`。
4. 提交：`git commit` 英文信息；`git status`/`git diff --stat` 确认范围，只 add 具体文件不 `-A`。
5. 自动 push 到 GitHub（约定）；若 push 被拒先 `git pull --rebase` 再推，冲突停下告知。

### 向后兼容
- 所有新接口加在 `/api` 前缀下，不破坏现有 `/api/ask`/`/api/knowledge-bases` 等。
- `DocumentOut` 新增字段为可选/有默认值，老前端不报错。
- 迁移用 `ADD COLUMN IF NOT EXISTS`，可重复执行。

### 验收总清单（完工标准）
- [ ] Dashboard 6 分区全真实数据，0 硬编码/随机
- [ ] Documents 上传人/权限范围/解析状态真实 + 服务端分页
- [ ] Search 筛选透传后端
- [ ] Graph 筛选联动 + 导出 + Top5/最近更新
- [ ] 部门树/标签/上传进度可用
- [ ] Reranker + 意图分类 + KG 回填 + 图谱推理生效
- [ ] 音频/视频/OCR 解析可检索
- [ ] 通知中心/系统设置/TTS 或 tracing 至少落地
- [ ] 全链路 `npm run build` 零错 + `pytest` 全绿

---

## 12. 建议执行顺序（最小可演示路径）

若时间紧，按此顺序保证每步都有可演示成果：
1. **P0 + P1 + P2**：Dashboard 全真实（最显眼，面试第一眼）。
2. **P3**：Documents 三列真实 + 分页（第二显眼）。
3. **P4**：Graph 导出/筛选（完整度）。
4. **P5**：部门树/上传进度（交互亮点）。
5. **P6**：Reranker/意图分类/KG（AI 深度，面试谈资）。
6. **P7/P8**：多模态 + 收尾（加分项）。
