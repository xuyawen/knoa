# 文档管理模块 开发清单（方案 A：延迟摄入）

> 整理自 2026-07-14 设计讨论。核心结论：**审核通过才切片入库**；**新增知识库入口放在文档管理页**；**审批流与上传捆绑为 P0**。

## 一、目标与设计原则

1. **方案 A（延迟摄入）**：上传只存原始字节（对象存储）+ `content_md` + 建 `Document(status=待复核)`，**不切分、不向量化、不写 DocChunk**。
2. **审核驱动摄入**：新增 `approve` 接口，翻转状态后触发摄入；`reject` 仅改状态、保留原始文件留痕。
3. **天然隔离**：检索器只从 `DocChunk` 按 `kb_id` 捞数据，未审核内容无 chunk，检索天然不可见 —— 后端改动极小。
4. **菜单级库**：知识库是比"文档"更上层的概念（合规管理 / 广告运营 / 物流 …），前端此前无"新建库"入口，需补齐。

## 二、后端改动

### 2.1 数据模型 `backend/app/models/knowledge.py`
- `Document.status` 枚举扩展：`待复核` / `已审核` / `已拒绝`（当前仅有前两者）。
- `Document` 新增字段（方案 A 必需）：
  - `storage_key`：对象存储原始文件 key，规范 `uploads/{kb_id}/{uuid}_{filename}`
  - `content_md`：解析后的 markdown 文本（上传即解析落库，供详情预览与后续摄入）
  - `original_filename`、`file_size`、`mime_type`
  - `reviewed_at`、`reviewed_by`（审批留痕）

### 2.2 对象存储 `backend/app/core/object_store.py`
- 确认 `LocalObjectStore` / `S3ObjectStore` 已支持 `put / get / delete`（已手写 SigV4，S3 兼容）。
- 新增上传即写 `storage_key`，删除时同步 `delete(storage_key)`。

### 2.3 摄入器重构 `backend/app/core/rag/ingestor.py`
- 抽出 `ingest_existing(doc)`：对已落库 `Document` 执行"切分 → 向量化 → 写 DocChunk → ES → 图谱"。
- `upload_document` 路径**移除同步摄入调用**，改为仅落库。
- `approve` 接口调用 `ingest_existing(doc)`。

### 2.4 路由 `backend/app/routers/knowledge.py`
| # | 方法 & 路径 | 说明 | 状态 |
|---|---|---|---|
| 1 | `POST /api/knowledge-bases` | 新增知识库（名称/图标/描述） | **待建** |
| 2 | `POST /api/knowledge-bases/{kb_id}/documents` | 上传文档，**只存不切**（方案 A） | 改（去摄入） |
| 3 | `GET /api/knowledge-bases/{kb_id}/documents` | 文档列表（含 status 角标数据） | 待确认/补 |
| 4 | `GET /api/knowledge-bases/{kb_id}/documents/{doc_id}` | 文档详情（返回 `content_md`） | **待建** |
| 5 | `POST /api/documents/{doc_id}/approve` | status→已审核 + 触发 `ingest_existing` | **待建** |
| 6 | `POST /api/documents/{doc_id}/reject` | status→已拒绝（保留原文件） | **待建** |
| 7 | `DELETE /api/documents/{doc_id}` | 级联清 DocChunk / 图谱 / ES + 删对象存储文件 | **待建** |

> 注意：`knowledge.py` 当前在路由体内直调 `get_llm()` 的坑已修（改用 `Depends(get_llm)`），新增接口务必沿用 `Depends` 写法，否则测试 override 失效。

### 2.5 检索器 `backend/app/core/rag/retriever.py`
- 现状已只按 `kb_id` 过滤，无 `status` 过滤 —— **方案 A 下零改动**，未审核内容天然隔离。✓

### 2.6 种子与测试
- `ingest_seed.py` 已建 5 个 KB（compliance/ads/logistics/selection/service）✓
- 补 pytest 用例：
  - 上传后 `DocChunk` 数量为 0（未摄入）
  - `approve` 后 `DocChunk` > 0 且检索可命中
  - `reject` 后 `Document` 仍在、状态正确、无 chunk
  - `DELETE` 后 chunk / ES / 图谱 / 对象存储均清空

## 三、前端改动

### 3.1 文档管理页（Documents 视图）
- 顶部 **"新增知识库"按钮**（置于该页下，非侧边栏）：点击弹窗 → 名称 / 图标 / 描述 → `POST /api/knowledge-bases`。
- 知识库列表网格：空态"暂无知识库"已做 ✓；新建后实时刷新。
- 点击某库 → 进入文档列表（文件名 / 状态角标 / 上传时间 / 大小）。
- **"上传文档"按钮** → 调 upload 接口（方案 A 只存，列表立即可见但检索不可见）。
- 文档行操作：**查看详情** / **审核通过** / **驳回** / **删除**。
- 详情抽屉：展示 `content_md` 文本。

### 3.2 AppSidebar
- 已有 KB 列表 + 空态 ✓；需确认新建库后侧边栏同步刷新。

## 四、优先级与依赖

**P0（核心闭环，必须一起做，缺一个链路就断）**
1. 新增知识库（页内按钮 + 弹窗 + 接口）
2. 文档列表（含 status）
3. 新增文档（方案 A：只存不切）
4. 文档详情（返回 content_md）
5. 审批流 `approve` / `reject`
6. 删除文档（级联清理）

**P1（体验增强）**
- 切片预览（approve 后看 chunk 分布）
- 重新向量化按钮（内容纠错后重切）

**P2（远期）**
- 多格式 / 批量上传
- 文档版本管理
- 列表筛选 / 检索重试 / 元数据编辑

## 五、验收标准

- [ ] 上传后**检索不到**该文档（未审核隔离生效）
- [ ] `approve` 后检索**可命中**
- [ ] `reject` 后文档留痕、不入库、原文件保留
- [ ] `DELETE` 后 chunk / ES / 图谱 / 对象存储**全清**
- [ ] 前端空态、状态角标、新建库刷新均正确
- [ ] CI 套件（pytest）全绿
