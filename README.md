# 知海 Knoa · 开发工作空间

跨境运营 AI 知识库（RAG 问答 + 答案溯源）的前端 / 后端工程。产品定位见 `docs/design-spec.md`。

## 技术栈
- **前端**：Vue 3 + Vite + TypeScript + vue-router + pinia
- **后端**：FastAPI（MVP 为 mock，预留 RAG 管线接口）
- **设计稿**：ardot `702429835416563`，含亮/暗桌面版 + 亮/暗移动端四版

## 目录结构
```
knoa/
├── docs/design-spec.md        # 设计规格（配色 / 字体 / 布局 / 组件 / 接口）
├── exports/                   # 设计稿导出图（4×PNG + 1×PDF）
├── frontend/                  # Vue 3 前端
│   └── src/
│       ├── components/        # 业务组件（Sidebar / TopBar / ChatStream / SourcePanel …）
│       ├── views/Workbench.vue# 桌面主工作台（三栏布局）
│       ├── composables/useTheme.ts  # 亮/暗主题切换（持久化 localStorage）
│       ├── mocks/data.ts      # mock 数据（问答 / 知识库 / 溯源 / 健康度 / 高频）
│       └── style.css          # 设计 Token（CSS 变量，亮/暗双主题）
└── backend/                   # FastAPI 后端
    ├── main.py                # 路由骨架（/api/ask 流式、/api/knowledge-bases、/api/trending）
    └── requirements.txt
```

## 启动前端
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

## 启动后端
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
前端 `vite.config.ts` 已将 `/api` 代理到 `localhost:8000`。

## 主题
亮/暗通过 `useTheme` 切换并持久化；所有配色集中在 `src/style.css` 的 CSS 变量，改色只动这一处。

## 进度
- [x] 设计规格文档（design-spec.md）
- [x] 前端骨架 + 亮/暗主题切换
- [x] 桌面主工作台 UI（mock 数据驱动，可直接预览）
- [ ] 后端联调（前端切到真实问答 API）
- [ ] 移动端适配（亮/暗移动版还原）
