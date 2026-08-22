# Knoa 生产部署与发版文档

> 本文件是生产发版的**唯一权威文档**，与部署脚本/配置同目录，随代码一起进仓库。
> 所有事实以**当前真实生产环境**为准（2026-07-31 最近一次发版已逐项验证）。

---

## 0. 一句话流程

```
本地改完代码 → commit + 双推（GitHub 走 CI + Gitee 供服务器拉） → SSH 服务器 git pull
→ docker compose -f docker-compose.prod-lean.yml up -d --build → 看迁移日志 → 验证
```

**只有用户明确说「部署 / 发版」才动生产服务器**，平时改动只在本地 commit + 推 Gitee，不要自作主张上线。

---

## 1. 生产环境事实（务必以此为准）

| 项 | 值 |
|----|----|
| 服务器 | 阿里云 ECS，公网 IP `8.134.14.177`，`root` 登录 |
| OS | 阿里云 Linux 3（RHEL8 兼容），Docker CE + compose v2 |
| 代码目录 | `/root/knoa` |
| 协议 | **纯 HTTP，仅 80 端口**（无 TLS、无 443、无 80→443 跳转） |
| 编排文件 | `docker-compose.prod-lean.yml`（**不是**默认 `docker-compose.yml`） |
| 容器 | 5 个：postgres / redis / backend / frontend / edge（nginx 反代） |
| 代码源 | **Gitee**（阿里云 ECS 出网连不上 GitHub）→ `https://gitee.com/xuyawenmy/knoa.git`，remote 名 `origin` |
| 最近发版 HEAD | `0acb186`（2026-08-22，移动端窄屏兜底收尾：名称单行/分页单行/图谱窄屏布局 + 会话置顶 + Chat keep-alive 等） |

> 服务器上 `git remote -v` 应看到 origin = `https://gitee.com/xuyawenmy/knoa.git`。若看到 github，说明环境被改过，发版前先 `git remote set-url origin https://gitee.com/xuyawenmy/knoa.git`。

---

## 2. 密钥与凭证路径（云服务密钥）

### 2.1 服务器 SSH 私钥（最重要，没有它连不上服务器）

- **本地路径**：`X:\workspace\knoa\deploy\knoa.pem`
- 已被 `.gitignore` 忽略（`*.pem`），**不会进仓库**
- 连接方式：`ssh -i deploy/knoa.pem root@8.134.14.177`
- **严禁**用本机 `~/.ssh/` 默认密钥（`id_ed25519` / `id_rsa`）连服务器，会被拒
- 新工作台必须能读到这个 `.pem` 才能 SSH；若在别的机器，需先把 `deploy/knoa.pem` 拷过去（妥善保管，别进 git）
- 首次连接加 `-o StrictHostKeyChecking=accept-new` 避免 host key 交互卡住

### 2.2 Gitee 代码仓库密钥（拉代码用）

- 本地 Gitee SSH key：`~/.ssh/id_ed25519`（公钥已加到 Gitee 账号 `xuyawenmy`）
- 服务器上 git remote 是 **Gitee HTTPS**，`git pull` 不需要 key；只有 `git push` 才要凭证
- 本机已配 `gitee` remote（SSH）：`git@gitee.com:xuyawenmy/knoa.git`

### 2.3 云服务 API 密钥（全部集中在 `backend/.env`）

- **文件位置**：本地 `X:\workspace\knoa\backend\.env`；生产 `/root/knoa/backend/.env`。两者都 gitignored（`.env`），**不会进仓库**。
- **包含哪些密钥项**（只列 key 名，值已填好，**不要打印/提交**）：

| 类别 | key 名 |
|------|--------|
| 大模型 LLM | `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` |
| 向量化 Embedding | `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` / `EMBEDDING_DIM`（阿里云百炼 DashScope） |
| 联网搜索 | `BOCHA_API_KEY` |
| 语音合成 TTS | `TENCENT_TTS_SECRET_ID` / `TENCENT_TTS_SECRET_KEY` / `TENCENT_TTS_REGION` |
| 对象存储 OSS | `OSS_ENABLED` / `OSS_BUCKET` / `OSS_ENDPOINT` / `OSS_REGION` / `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` |
| 链路追踪 | `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT`（仅生产开启） |
| 鉴权 | `JWT_SECRET` / `ADMIN_PASSWORD` / `ADMIN_USERNAME` |
| 数据库 | `DATABASE_URL`（compose 里会被 `environment` 覆盖为容器内地址） |
| 应用 | `APP_ENV` / `CORS_ORIGINS` / `LOG_LEVEL` |

- ⚠️ 发版**不需要改这些 key**，已填好。改了 key 必须重启 backend 才生效（`env_file` 在 `up` 时读取）。
- ⚠️ **切勿把任何 key 的值写进会被提交的文档 / 日志 / 回复里**。

### 2.4 配置模板（非密钥，可提交）

- `deploy/.env.production-template`：生产 `.env` 模板（含 `PUBLIC_IP=8.134.14.177`、`CORS_ORIGINS=http://8.134.14.177`、`TLS_MODE=http`、`TRUST_PROXY=true`）
- `deploy/.env.example`：通用示例

---

## 3. 发版标准流程（每次都一样）

```bash
# 1) 本地：确认改动已 commit，同时推两个仓库（内容必须一致）
git push origin master       # GitHub → 触发 CI（build + pytest + alembic check）
git push gitee master        # Gitee → 生产服务器从这里 pull（阿里云连不上 GitHub）

# 2) SSH 上服务器
ssh -i deploy/knoa.pem -o StrictHostKeyChecking=accept-new root@8.134.14.177

# 3) 拉最新代码（确认 HEAD 是目标 commit）
cd /root/knoa && git pull origin master && git log --oneline -1

# 4) 重建并启动（backend 镜像重新 build，含新迁移）
docker compose -f docker-compose.prod-lean.yml up -d --build

# 5) 看日志，确认迁移跑通
docker compose -f docker-compose.prod-lean.yml logs --tail=40 backend
# 必须看到： init_db: alembic upgrade head done

# 6) 验证（见第 5 节）
```

> 整个 build + 启动约 1 分钟（镜像层缓存命中时更快）。

> **本地推 GitHub 失败（SSH 22 被墙）时**：本机网络 `github.com:22` 不通、`ssh.github.com:443` 可达。标准解法是在 `~/.ssh/config` 加 `Host github.com / Hostname ssh.github.com / Port 443`（不改 remote、可逆）；或临时只推 Gitee 先上线，GitHub 待网络可达后补推（`git push origin master`）。只推 Gitee 时 CI 门禁不跑，需自行确保本地 build/test 已过。

---

## 4. 启动期必知

- **迁移自动跑**：`main.py` 的 lifespan 启动会执行 `alembic upgrade head`，日志打 `init_db: alembic upgrade head done`，不必手动 migrate。
  ⚠️ 若看到 `init_db: alembic unavailable, fallback create_all` 警告，说明迁移**没跑**（init_db 捕获异常后兜底静默建表），增量 schema 未生效——必须立即排查 alembic 为何失败，**不能当作正常启动**。
- **生产强校验**：`APP_ENV=production` 触发 `validate_production_settings()`，若 `JWT_SECRET` / `ADMIN_PASSWORD` 还是默认值（dev-change-me / admin123）会**直接 fail-fast 启动失败**。看 backend 日志定位哪一项不合格。
- **Cookie**：`COOKIE_SECURE` 在 `config.py` 硬编码 `False`（纯 HTTP 必需，否则浏览器拒收 cookie、登录被打破）。
- **CORS**：`CORS_ORIGINS` 必须等于浏览器实际访问地址（生产 = `http://8.134.14.177`），否则前端接口被 CORS 拦截 → 401 → 页面报错。
- **文档接口在生产关闭**：`/docs`、`/redoc`、`/openapi.json` 在 `APP_ENV=production` 下返回 404，属正常，**不是故障**。

---

## 5. 验证清单（上线后必做）

```bash
# 容器状态（应全部 healthy / Up）
docker compose -f docker-compose.prod-lean.yml ps

# 后端健康检查（经 edge 反代）
curl -fsS http://127.0.0.1/api/health        # → {"status":"ok",...}

# 边缘反代根路径
curl -o /dev/null -w 'edge=%{http_code}\n' http://127.0.0.1:80/      # 期望 200

# 鉴权链路（无 token 应 401，证明反代+鉴权通）
curl -o /dev/null -w 'kb=%{http_code}\n' http://127.0.0.1:80/api/knowledge-bases   # 期望 401
```

> 外部访问验证：让用户在浏览器**关掉本地代理直连** `http://8.134.14.177`，或 SSH 服务器本地 `curl 127.0.0.1:80`。
> 注意：本机沙箱 curl 公网 IP 会返回 `000` / exit 7（出网受限），**不可用此判定服务器存活**；判活以服务器内 `curl 127.0.0.1` 为准。

### 5.1 涉及迁移时核验 DB schema

```bash
# 例：确认某列已删 / 某表已建
docker compose -f docker-compose.prod-lean.yml exec -T postgres \
  psql -U knoa -d knoa -c "SELECT column_name FROM information_schema.columns WHERE table_name='knowledge_base';"
docker compose -f docker-compose.prod-lean.yml exec -T postgres \
  psql -U knoa -d knoa -c "SELECT to_regclass('public.error_event') AS error_event;"
```

### 5.2 复杂查询：写 SQL 文件 + scp，别在命令行内联

PowerShell → ssh → bash → psql 多层嵌套引号极易被吞（`count(*)` 会被 PowerShell 当通配符展开）。**正确做法**：

```bash
# 1) 本地把查询写成文件（可用 psql 的 \echo 打小节标题）
#    例如 _verify.sql

# 2) 上传到服务器
scp -i deploy/knoa.pem _verify.sql root@8.134.14.177:/root/knoa/_verify.sql

# 3) 通过 stdin 喂给容器内 psql，跑完删临时文件
ssh -i deploy/knoa.pem root@8.134.14.177 \
  "cd /root/knoa && docker compose -f docker-compose.prod-lean.yml exec -T postgres psql -U knoa -d knoa < _verify.sql && rm -f _verify.sql"
```

---

## 6. 注意事项（踩过的坑）

1. **阿里云连不上 GitHub**：服务器只能从 Gitee 拉代码。本地发版需**双推**——`git push origin master`（GitHub，触发 CI）+ `git push gitee master`（Gitee，供服务器 pull），两边代码保持一致；切勿只推一边（只推 Gitee 则 CI 不跑，门禁形同虚设）。
2. **别用默认 compose**：生产用 `docker-compose.prod-lean.yml`，不是 `docker-compose.yml`。
3. **纯 HTTP**：nginx edge 只映射 `80:80`，不要加 443 / TLS / 跳转。
4. **ORM 改动必须出迁移**：任何改列 / 改默认值都要生成 alembic 迁移，否则 CI 的 `alembic check` 会红（曾因此部署失败）。迁移里 `DROP COLUMN` 建议写成 `ALTER TABLE x DROP COLUMN IF EXISTS y` 做幂等。
5. **不要每次改代码都上服务器重建**：只有用户明确「部署」才动生产。平时改动只在本地 commit + 推 Gitee。
6. **后端内存 768M 是风险点**：2GB 机器上 Python 处理大请求（文档上传 / SSE 流式）可能 OOM。若频繁 restart，考虑升级内存或加 swap。
7. **密钥文件不进 git**：`.env`、`*.pem` 都已被 `.gitignore` 忽略。提交前 `git status` 确认没有这些文件被 staged。
8. **前端构建走国内镜像**：镜像源写在 `frontend/Dockerfile` 第 6 行 `ENV npm_config_registry=https://registry.npmmirror.com`（服务器上**并无** `frontend/.npmrc` 文件），build 走 npmmirror 才快。
9. **healthcheck / curl 别用 `localhost`**：alpine 容器内 `localhost` 优先解析到 `::1`（IPv6），而 nginx `listen 80;` 只听 IPv4 → 连接被拒 → 容器被误标 unhealthy（服务其实正常）。统一用 `http://127.0.0.1/`；新增 nginx 类容器健康检查直接用 IPv4。
10. **fail-close 权限收紧（2026-07-31 上线）**：`security.py` 移除了「无授权记录即全员可见的开放库」隐式 view，未授权库对非超管返回不可见。上线前须排查存量「无授权开放库」并补授权。
    **本次生产已核验为零风险**：全部 8 个库（法务/物流/运营/HR/研发/财务/客服/产品）各有 1 条用户授权 + 1 条部门授权，无任何无授权开放库。排查 SQL 见 5.2（`NOT EXISTS kb_permission AND NOT EXISTS kb_dept_grant`）。

---

## 7. 回滚方案

```bash
# 代码回退到上一可用版本
cd /root/knoa && git checkout <上一commit>
docker compose -f docker-compose.prod-lean.yml up -d --build

# 数据库向下迁移（把删掉的列加回去）
docker compose -f docker-compose.prod-lean.yml exec -T backend alembic downgrade <目标revision>
# 注：downgrade 会重新 ADD COLUMN（带 server_default），结构可恢复；
#     但 DROP COLUMN 类迁移 downgrade 只加回空列，已删数据不可逆。
```

---

## 8. 快速参考卡

```bash
# ═══ 上线 ═══
ssh -i deploy/knoa.pem root@8.134.14.177
cd /root/knoa && git pull origin master
docker compose -f docker-compose.prod-lean.yml up -d --build

# ═══ 看日志 ═══
docker compose -f docker-compose.prod-lean.yml logs -f backend

# ═══ 进数据库 ═══
docker compose -f docker-compose.prod-lean.yml exec -T postgres psql -U knoa -d knoa

# ═══ 进后端 shell ═══
docker compose -f docker-compose.prod-lean.yml exec backend sh

# ═══ 容器状态 / 健康 ═══
docker compose -f docker-compose.prod-lean.yml ps
curl -fsS http://127.0.0.1/api/health
```
