# Knoa 运维手册（Runbook）

> 配套：[架构](./architecture.md) · [API 参考](./api.md)
> 编排文件：`docker-compose.yml`（生产 base）+ `docker-compose.dev.yml`（开发覆盖）。
> 生产 TLS 反代细节见 `deploy/nginx/README.md`。

---

## 0. 前置

- Docker + Compose v2（`docker compose` 子命令）。
- 后端密钥在 `backend/.env`（从 `.env.example` 复制，**已被 gitignore**）。
- 生产必改 `.env`：`JWT_SECRET`、`ADMIN_PASSWORD`（默认弱值可被伪造/冒认）、`CORS_ORIGINS`（填你的域名）、LLM/Embedding 的 key。

---

## 1. 启动 / 停止 / 重启

### 生产（推荐）

```bash
# 首次：先放 TLS 证书（自签仅测试；生产用 deploy/nginx/README.md 的 certbot 步骤）
bash deploy/nginx/generate-selfsigned.sh      # 生成 deploy/nginx/certs/{fullchain,privkey}.pem

# 构建并后台启动（edge + backend + frontend + postgres + redis + 每日备份）
docker compose up -d --build

# 看状态 / 日志
docker compose ps
docker compose logs -f backend        # 实时看后端日志（含 [web_search] / [ask] 等）
docker compose logs -f edge           # 反代 / TLS 报错看这里

# 停止 / 重启单个服务
docker compose stop backend
docker compose restart backend
docker compose down                     # 停并删容器（数据在卷里，不丢）
```

> 生产模式下 **只有 `edge` 暴露 80/443**；postgres/redis/backend/frontend 只在容器网络内，不发布宿主机端口。

### 本地开发

```bash
# 恢复 pg(5433)/redis(6380)/frontend(8080) 的宿主机端口，关闭 edge/backup
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
# 或直接本机跑：backend 用 venv 的 uvicorn（见根 README 快速开始），frontend 用 npm run dev(5174)
```

---

## 2. 数据库迁移（Alembic）

Schema 以 Alembic 迁移为准（`backend/migrations`，初始迁移 `eb70aefd7b19`）。

```bash
cd backend
uv run python -m alembic -c alembic.ini upgrade head     # 落到最新
uv run python -m alembic -c alembic.ini check         # 校验模型与迁移一致（无待生成迁移）
uv run python -m alembic -c alembic.ini history       # 看已应用迁移链
```

- **首次启动** backend 还会执行 `init_db()`（`create_all` 幂等兜底），新建的表自动建；**现有表加列** `create_all` 不会补，需手写一次性 `ALTER` 脚本（参考历史做法：查 `information_schema.columns` 判存在再 `ADD COLUMN ... NOT NULL DEFAULT`，旧行自动回填）。
- 改了 `app/db` 模型后，**务必** `alembic revision --autogenerate` 生成新迁移，别只靠 `create_all`。
- 迁移契约由 CI 的 `backend` job 守卫（`upgrade head` + `check`）。

---

## 3. 备份 / 恢复（PostgreSQL）

### 自动备份

`backup` 服务（postgres:16 镜像）每 24h 跑 `deploy/backup/pg-backup.sh`：
`pg_dump --format=plain --no-owner --no-privileges` → gzip → `knoa_YYYYMMDD_HHMMSS.sql.gz`，
保留 `BACKUP_RETENTION_DAYS=7` 天（超期 `find -mtime` 删）。落盘在 `knoa_backups` 卷。

```bash
docker compose exec backup ls -1t /backups        # 看已有备份
docker compose exec backup sh -c '/usr/local/bin/pg-backup.sh'   # 手动触发一次
```

### 手动备份（脱离容器）

```bash
# 从宿主机对运行中的 postgres 服务做一次性 dump
docker compose exec -T postgres pg_dump -U knoa knoa | gzip > knoa_manual_$(date +%Y%m%d).sql.gz
```

### 恢复

备份是 **plain SQL**（不是 custom/archive 格式），用 `psql` 回放：

```bash
# 1) 停写（避免恢复期间有新写入），可选
# 2) 清空目标库后回放（plain dump 已含 CREATE TABLE，先 drop 干净再导）
docker compose exec -T postgres psql -U knoa -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
gunzip -c knoa_20260713_010000.sql.gz | docker compose exec -T postgres psql -U knoa knoa

# 3) 重启 backend 让连接池/缓存刷新
docker compose restart backend
```

> 恢复会覆盖现有数据。生产恢复前务必先另存一份当前备份。

---

## 4. TLS 证书

- 证书在宿主机 `deploy/nginx/certs/`，bind mount 进 `edge` 容器（`/etc/nginx/certs:ro`），**不进镜像、不进 git**。
- 换证书**无需重建容器**：放好同名文件后 `docker compose exec edge nginx -s reload` 热加载。
- certbot 续期：`certbot renew` → 复制新 `fullchain.pem`/`privkey.pem` 到 `deploy/nginx/certs/` → reload。
- 自签仅本地测试：`bash deploy/nginx/generate-selfsigned.sh`。

---

## 5. 常见坑 / 排错

| 现象 | 根因 / 处理 |
| --- | --- |
| `edge` 一直 restart | `deploy/nginx/certs/` 缺 `fullchain.pem`/`privkey.pem`，nginx 起不来。先放证书再 `up`。 |
| 流式回答被攒批、一次性吐出 | SSE 缓冲。确认 `deploy/nginx/nginx.conf` 的 `location /api/` 有 `proxy_buffering off;`（改完 `edge nginx -s reload`）；开发用 vite 时其 proxy 已删 `content-encoding`。 |
| 浏览器 CORS 报错 | 后端 `CORS_ORIGINS` 必须等于站点访问 Origin（如 `https://knoa.example.com`）。compose 生产环境已用 `environment` 覆盖，改那里或 `.env`。 |
| 登录 401 / 令牌无效 | `JWT_SECRET` 不一致或过期；admin 由首次启动（无用户时）用 `.env` 的 `ADMIN_USERNAME/ADMIN_PASSWORD` 自动建，**改密码要在首次启动前**改好。 |
| 上传文档 415 / 解析失败 | 扩展名不在 md/txt/docx/pdf；pdf 需部署环境装了 `pypdf`（沙箱无 → 抛 UnsupportedFormatError）。 |
| 文档不进 ES / 检索只走 pgvector | `ES_ENABLED` 未 True，或该 KB 索引不存在（上传路径已补 `ensure_index`；seed 前确保 ES 可达）。ES 不可达时**自动回退 pgvector，不崩**。 |
| 记忆 / 图谱不生效 | LLM 或 Embedding 不可达时**静默降级跳过**，不报错。查后端日志确认 key 有效。 |
| 改了 `.py` 没生效 | uvicorn **无 `--reload`**，必须手动 `docker compose restart backend`（或本机重跑进程）。 |
| `alembic check` 报漂移 | 模型改了但没生成新迁移。先 `alembic revision --autogenerate` 再 `upgrade head`。 |
| 容器重启后数据在 | 数据在命名卷 `knoa_pgdata`/`knoa_redisdata`/`knoa_uploads`；`docker compose down` 不删卷。真要清：`docker compose down -v`（**危险，先备份**）。 |

---

## 6. 健康检查与冒烟

```bash
curl -kI https://localhost/api/health      # 期望 200，且响应头带 Strict-Transport-Security
curl -k  https://localhost/api/trending  # 期望返回高频问题数组
# 登录 → 建库 → 上传 → 问答（端到端需 LLM/Embedding key 有效）
```

- CI 已覆盖：后端 `compileall` + `import app.main` + `alembic upgrade/check` + **pytest 7 passed**（API 冒烟 / SSE 问答 / 混合检索 / 迁移契约），无需任何 API key（LLM/Embedder/Redis 由 `conftest` 的 `dependency_overrides` 换测试替身）。
