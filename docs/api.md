# Knoa API 参考

> 配套：[架构](./architecture.md) · [运维手册](./runbook.md)
> 所有路径前缀 `/api`。前端封装见 `frontend/src/api/index.ts`。

## 基础约定

- **Base URL**：生产由 `edge` 反代在站点根（如 `https://knoa.example.com/api/...`）；开发 `https://localhost:5174/api/...`（vite proxy）。
- **认证**：除 `/health`、`/auth/login`、`/sources/{chunk_id}`、`/trending` 外，均需在请求头带 `Authorization: Bearer <token>`（登录拿 token 见下）。
- **请求体**：`application/json`。上传文档走 JSON 文本（`{filename, content_b64}`），**不用 multipart**（避开受限环境的 multipart 依赖）。
- **错误**：统一 `{ "detail": "..." }`，HTTP 4xx/5xx。

---

## 认证 `/auth`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/auth/login` | 否 | 登录。body `{username, password}` → `{access_token, token_type:"bearer"}` |
| GET | `/auth/me` | 是 | 当前用户（`UserOut`：id/用户名/显示名/角色/启用状态） |
| GET | `/auth/users` | admin | 用户列表 |
| POST | `/auth/users` | admin | 新建用户（201）。body `{username, password, display_name?, role}` |
| PATCH | `/auth/users/{user_id}` | admin | 改角色/启用停用/重置密码。保护：不能删/停用最后一个 admin |
| DELETE | `/auth/users/{user_id}` | admin | 删除用户（204）。保护：不能删自己、不能删最后一个 admin；级联清 KBPermission / Memory / ChatSession |

> 登出是**前端行为**（清 localStorage token），无后端失效端点（JWT 无状态，靠过期 `JWT_EXPIRE_MINUTES`）。

---

## 知识库 `/knowledge-bases`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/knowledge-bases` | 是 | 库列表（按当前用户权限过滤；含文档数 / 待复核数 / 健康度） |
| POST | `/knowledge-bases` | admin/editor | 新建库（201）。创建者自动获该库 admin 级库级权限 |
| GET | `/knowledge-bases/{kb_id}/documents` | 是+库权限 | 某库文档列表（标题 / 状态 `已审核`\|`待复核` / 来源） |
| POST | `/knowledge-bases/{kb_id}/documents` | 是+库权限 | 上传文档（201）。body `{filename, content_b64}`（或旧 `{filename, content}`）。支持 `.md/.txt/.docx/.pdf`，按扩展名解析 |

> 当前**无**「库详情 GET」「库删除」端点 —— 列表已含所需元信息。

---

## 问答 `/ask`（SSE 流式）

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/ask` | 是+库权限 | 流式问答。body `{question, knowledgeBase?, sessionId?}` |

**SSE 事件**（CRLF 分隔，`event:` / `data:` 行；前端 `replace(/\r\n/g,'\n')` 后按 `\n\n` 切分）：

| event | data 形状 | 含义 |
| --- | --- | --- |
| `thinking` | `{step, action, content?}` | Agent 决策/思考过程（如 `retrieve` / `web_search` / `direct_answer`） |
| `sources` | `[{id, title, content, source_type:"kb"\|"web"\|"graph", url?, chunkId?}]` | 命中片段，对应答案内联引用 `[1][2]` |
| `delta` | `{text}` | 答案逐字增量 |
| `ping` | `{}` | 心跳（前端保活） |
| `done` | `{messageId, sessionId}` | 结束，带消息/会话 id |
| `error` | `{message}` | 出错（如超时、知识库无权限） |

> 约 90s 内无新 token 前端会本地超时（复杂问题 Agent 多步决策会更久，前端已放宽到 180s）。

---

## 溯源 `/sources`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/sources/{chunk_id}` | 否（公开） | 溯源详情。按 `DocChunk` 的 UUID 返回 `{content, document_title, kb_id, kb_name}`，供前端抽屉展示原文 |

---

## 会话历史 `/sessions`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/sessions` | 是（本人） | 会话列表：id / 标题（无标题回退首条消息）/ 更新时间 / 消息数 |
| POST | `/sessions` | 是 | 新建空会话（201）。body `{title?}` |
| GET | `/sessions/{session_id}` | 是（本人） | 会话详情：全部消息（按时间正序）+ 引用 |

---

## 反馈 `/feedback`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/feedback` | 是 | 对某条回答反馈。body `{messageId, rating:"up"\|"down"}` |
| DELETE | `/feedback/{message_id}` | 是 | 撤销该回答的反馈 |

---

## 长期记忆 `/memories`（Mem0 轻量自研版）

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/memories` | 是（本人） | 当前用户的长期记忆列表 |
| DELETE | `/memories/{memory_id}` | 是（本人） | 删除单条记忆 |
| DELETE | `/memories` | 是（本人） | 清空本人全部记忆 |

> 记忆由系统在每轮问答后**后台自动抽取+保存**（向量余弦>0.92 判为同一条则覆盖）；本组端点仅供查看/清理。

---

## 高频问题 `/trending`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/trending` | 否（公开） | 高频问题排行（已过滤打招呼/闲聊）。来自 Redis sorted set 实时计数 |

---

## 健康检查 `/health`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/health` | 否（公开） | 返回 `{"status":"ok","service":"knoa-backend"}`，供 edge/健康检查与 CI 用 |
