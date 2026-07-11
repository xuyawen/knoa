# 知海 Knoa · 设计规格文档（Design Spec）

> 对应 ardot 设计文件：`702429835416563`（四版：亮/暗桌面 + 亮/暗移动端）
> 导出物：`exports/` 目录（4 张 2x PNG + 1 份合并 PDF），开发吸色/对标以 PNG 为准
> 版本：v1 ｜ 更新：2026-07-11 ｜ 技术栈：Vue 3 + Vite + TS 前端 / FastAPI 后端

---

## 1. 产品概览

- **名称**：知海 Knoa · 跨境运营 AI 知识库
- **定位**：中大型跨境电商公司运营团队的知识大脑。基于 RAG 的运营知识问答 + 答案溯源，覆盖合规、广告、物流、选品、客服、财务六大知识域。
- **当前 MVP**：桌面主工作台（左侧导航 + 中间问答 + 右侧溯源），亮/暗双主题。
- **内网使用**：无需商标，logo 用「知」字标即可。

---

## 2. 设计 Token（Design Tokens）

### 2.1 配色 · 亮色主题（Light）

| Token | 用途 | 色值 |
|-------|------|------|
| `--bg-page` | 页面背景 | `#F9F9F9` |
| `--bg-subtle` | 侧栏 / 浅面板 | `#F2F4F7` |
| `--bg-surface` | 卡片 / 白面 | `#FFFFFF` |
| `--border` | 描边 / 分割线 | `#EAEAEA` |
| `--brand` | 品牌主色（蓝） | `#014DB2` |
| `--brand-hover` | 主色 hover | `#013A87` |
| `--brand-soft` | 主色浅底（选中/高亮） | `#E6F0FF` |
| `--text-primary` | 正文文字 | `#0A1628` |
| `--text-secondary` | 次要文字 | `#5C6B82` ⚠️推断 |
| `--text-placeholder` | 占位文字 | `#8A97AC` ⚠️推断 |
| `--danger` | 合规告警红 | `#EF4444` |
| `--success` | 可信绿 | `#10B981` |

### 2.2 配色 · 暗色主题（Dark，实测值）

| Token | 用途 | 色值 |
|-------|------|------|
| `--bg-page` | 页面背景 | `#0B1220` |
| `--bg-subtle` | 次级面板 | `#151E30` |
| `--bg-surface` | 卡片 / 白面 | `#1B2538` |
| `--border` | 描边 / 分割线 | `#243044` |
| `--brand` | 品牌主色（提亮蓝） | `#3B82F6` |
| `--brand-hover` | 主色 hover | `#2F6FE0` |
| `--brand-soft` | 主色浅底 | `#15233B` |
| `--text-primary` | 正文文字 | `#E8EDF5` |
| `--text-secondary` | 次要文字 | `#8A97AC` |
| `--text-placeholder` | 占位文字 | `#5C6B82` |
| `--danger` | 合规告警红 | `#F87171` |
| `--success` | 可信绿 | `#34D399` |

> ⚠️ 亮色主题 `--text-secondary` / `--text-placeholder` 为推断值，开发时以 `exports/2_3.png` 吸色校准为准。暗色主题为实测值（163 处改色逐一核对）。

### 2.3 字体（Typography）

- **西文 / 数字**：`Inter`（正文）、`Outfit`（标题 / 品牌）
- **中文**：系统字体栈 `PingFang SC / Microsoft YaHei / Noto Sans SC`
- **字号梯度**：

  | 级别 | 用途 | 字号 / 字重 |
  |------|------|-------------|
  | XL | 品牌 / 大标题 | 24px / 600 |
  | L | 区域标题 | 18px / 600 |
  | M | 卡片标题 | 15px / 600 |
  | Body | 正文 | 14px / 400（行高 1.6） |
  | Caption | 标注 / 次要 | 12px / 400 |

- **字重**：400 常规、500 中、600 半粗
- **引入**：通过 npm `@fontsource/inter` + `@fontsource/outfit`，或 Google Fonts `<link>`

### 2.4 间距 / 圆角 / 阴影

- **间距基数**：4px 栅格（4 / 8 / 12 / 16 / 24 / 32）
- **圆角**：`sm` 6px · `md` 10px · `lg` 14px · `pill` 999px
- **阴影（亮色）**：卡片 `0 1px 3px rgba(10,22,40,0.06)`；浮层 `0 8px 24px rgba(10,22,40,0.12)`
- **阴影（暗色）**：卡片 `0 1px 3px rgba(0,0,0,0.3)`；浮层 `0 8px 24px rgba(0,0,0,0.5)`

### 2.5 桌面布局尺寸

| 区域 | 宽度 | 说明 |
|------|------|------|
| 整体画板 | 1440 × 900 | 设计基准 |
| 左侧栏 | 240px | 顶到底，固定 |
| 顶栏 | 全宽 × 64px | 底部 1px 分割线 |
| 中间问答区 | flex 1（≈880px） | 1440 − 240 − 320 |
| 右侧溯源面板 | 320px | 固定 |

---

## 3. 桌面主工作台页面结构（左→右三栏 + 顶栏）

### 3.1 左侧栏（240px）
- **品牌区**：logo「知」字标 + 「知海 Knoa」+ 折叠箭头
- **工作区切换**：当前「全部知识」
- **五大知识库导航**（图标 + 名称 + 可选角标）：
  1. 合规库（红色角标「5 份待复核」）
  2. 广告投放
  3. 物流仓储
  4. 选品策略
  5. 客服话术
- **工作区入口**（次级分组）：我的收藏 / 最近浏览 / 团队共享
- **底部用户卡**：头像 + 姓名 + 角色 + 设置入口

### 3.2 顶栏（64px）
- **左**：当前标题「全部知识」+ 副标题 / 计数
- **中**：全局提问框（占位「向知海提问，⌘K 唤起」+ 搜索图标）
- **右**：通知铃 + 账户头像

### 3.3 中间问答区（flex 1）
- **对话流**：用户问 + AI 答（含引用角标 `[1]` `[2]`）
- **AI 答底部栏**：引用来源 chip + 反馈（👍 / 👎 / 复制）+ 署名「知海 · 运营知识助手」
- **输入栏（底部固定）**：多行输入 + 发送按钮 + 附件 / 知识域选择

### 3.4 右侧溯源面板（320px）
- **标题**：「答案溯源」
- **来源卡片列表**：每条 = 知识库名 + 文档标题 + 匹配片段 + 置信度
- **知识库健康度**：各库文档数 / 更新时间 / 覆盖率小条
- **高频问题榜**：本日 Top 问题列表（可点击追问）

---

## 4. 组件清单（Component Inventory）

| 组件 | 位置 | 关键 props / 说明 |
|------|------|-------------------|
| `AppSidebar` | 左栏 | `collapsed`, `activeBase`, `pendingCounts` |
| `BrandMark` | 品牌区 | logo「知」+ 名称，可折叠 |
| `KnowledgeNavItem` | 左栏 | `icon`, `name`, `badge?`（如「5 份待复核」红色） |
| `TopBar` | 顶栏 | `title`, `subtitle`, `onAsk` |
| `GlobalSearch` | 顶栏中 | `placeholder`, `shortcut="⌘K"`, `onSubmit` |
| `ChatStream` | 中区 | `messages[]`（role/user/assistant, content, citations[]） |
| `MessageBubble` | 中区 | `role`, `content`, `citations` |
| `CitationChip` | 中区/答底 | `index`, `onClick` → 定位右侧溯源卡 |
| `FeedbackBar` | 答底 | `onLike`, `onDislike`, `onCopy` |
| `Composer` | 输入栏 | `v-model`, `onSend`, `knowledgeBase?` |
| `SourcePanel` | 右栏 | `sources[]`, `health[]`, `trending[]` |
| `SourceCard` | 右栏 | `kb`, `title`, `snippet`, `confidence` |
| `HealthBar` | 右栏 | `kb`, `docCount`, `updatedAt`, `coverage` |
| `TrendingList` | 右栏 | `questions[]`, `onAsk` |
| `ThemeToggle` | 顶栏/设置 | `theme`, `onToggle`（持久化 localStorage） |

---

## 5. 交互说明

- **提问**：`⌘K` 全局唤起提问框；Enter 发送，Shift+Enter 换行
- **回答**：流式输出（typing 效果），引用角标可点击定位右侧溯源卡片
- **引用展开**：右侧面板卡片可展开看完整匹配片段
- **反馈**：👍 / 👎 收集；👎 触发「哪里不对」轻量表单
- **主题切换**：右上角或设置内切换亮/暗，持久化 `localStorage`
- **知识库角标**：合规库「待复核」红点实时（接后端统计接口）

---

## 6. 路由规划

**MVP**
- `/` 或 `/workbench` → 桌面主工作台

**后续**
- `/knowledge` → 知识库列表
- `/knowledge/:id` → 知识库详情（文档列表 / 上传 / 向量化）
- `/ask/:sessionId` → 问答会话（移动端复用同一组件）

---

## 7. 后端接口预留（FastAPI）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/ask` | 问答。请求 `{question, knowledge_base?, session_id}`；响应 **SSE 流式** `{delta}` + 末尾 `{sources}` |
| `GET` | `/api/knowledge-bases` | 知识库列表（含统计 / 待复核数） |
| `POST` | `/api/documents` | 上传文档 |
| `POST` | `/api/documents/:id/index` | 触发切分 + 向量化 |
| `GET` | `/api/sources/:answerId` | 溯源详情 |
| `GET` | `/api/trending` | 高频问题榜 |

**RAG 管线**：文档 → 切分 → 向量库（Chroma / Qdrant）→ 检索 → LLM 生成（带引用）。
**MVP 策略**：先用 mock 数据跑通前端交互，后端接真实 LLM / 向量库后置（接口签名先固定）。

---

## 附录 A：开发对标物路径

- 亮色桌面：`exports/2_3.png`
- 亮色移动：`exports/5_2.png`
- 暗色移动：`exports/5_126.png`
- 暗色桌面：`exports/6_2.png`
- 合并预览：`exports/跨境运营AI知识库.pdf`
- 设计源文件：`https://ardot.tencent.com/file/702429835416563`
