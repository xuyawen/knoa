# Knoa 生产环境部署指南（腾讯云过渡期 · 2C2G）

> **适用服务器**：腾讯云 CVM 2核 2G / WS2016 DataCenter / 170.106.74.73
> **过渡期**：~11 天（到期 2026-08-04），之后迁移阿里云
> **部署方式**：Docker Compose（低资源裁剪版 `docker-compose.prod-lean.yml`）

---

## 一、资源分配总览

| 服务 | CPU | 内存 | 说明 |
|------|-----|------|------|
| Windows Server 2016 | — | ~1 GB | 操作系统基线（无法压缩） |
| Docker Desktop | — | ~300 MB | Hyper-V 虚拟化层 |
| postgres (alpine) | 1 核 | 512 MB | shared_buffers=64MB，低内存调优 |
| redis (alpine) | 0.25 核 | 96 MB | 无持久化，maxmemory=64MB |
| backend (Python) | 1.5 核 | 768 MB | 单 worker uvicorn |
| frontend (nginx) | 0.25 核 | 128 MB | 静态文件服务 |
| edge (nginx 反代) | 0.25 核 | 64 MB | TLS 终止 + API 转发 |
| **容器合计** | **3.5 核** | **~1.57 GB** | |
| **系统总计** | | **~2.9 GB** | 踩着 2GB 线跑，依赖 OS 内存压缩 |

> **风险提示**：backend 的 768M 是最大风险点。Python/uvicorn 在处理大请求（文档上传/SSE 流式）时内存可能飙升。如果频繁 OOM，考虑：(1) 升级到 4G 内存（推荐）；(2) 进一步压到 512M 但增加 swap。

---

## 二、服务器初始化（逐步操作）

### Step 1：连接服务器

```powershell
# 用腾讯云控制台的默认管理员账号（Administrator）+ 初始密码登录
# 登录后第一时间改密码
```

### Step 2：安装 Docker Desktop for Windows

WS2016 需要 Docker Desktop 4.x（最后一个支持 WS2016 的版本）：

```powershell
# 1. 安装 DockerMsftProvider（来自 PowerShell Gallery）
Install-Module -Name DockerMsftProvider -Force
Install-Package -Name docker -ProviderName DockerMsftProvider -Force

# 2. 或直接下载 Docker Desktop（推荐，有 GUI 更好管理）
#    下载地址：https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe
#    安装时勾选 "Use WSL 2 instead of Hyper-V" —— 但 WS2016 不支持 WSL 2，
#    所以必须用 Hyper-V（安装时会自动启用）

# 3. 启用 Hyper-V（如果还没开）
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All

# 4. 重启计算机
Restart-Computer -Force
```

重启后验证：

```powershell
docker version
docker-compose version   # Docker Desktop 自带 compose v2（docker compose 命令）
```

### Step 3：配置 Docker 镜像加速（腾讯云内网源，拉取速度提升 10x+）

打开 Docker Desktop → Settings → Docker Engine，加入：

```json
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com"
  ]
}
```

点击 Apply & Restart。

### Step 4：防火墙放行端口

```powershell
# 放行 HTTP/HTTPS（入站规则）
New-NetFirewallRule -DisplayName "Knoa HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "Knoa HTTPS" -Direction Inbound -LocalPort 443 -Action Allow

# 放行 SSH（远程管理用，限制来源 IP 更安全）
New-NetFirewallRule -DisplayName "SSH" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow
```

同时去**腾讯云控制台 → 安全组**，确认入站规则允许 TCP 80/443。

### Step 5：创建项目目录并上传代码

```powershell
# 创建目录结构
mkdir C:\knoa\deploy\nginx\certs
mkdir C:\knoa\deploy\nginx\certbot

# 上传项目文件（以下任选一种方式）：
#
# 方式 A：git clone（推荐）
cd C:\knoa
git clone https://github.com/xuyawen/knoa.git .
# 如果仓库是私有的，需要先配 Git Credential 或用 SSH key
#
# 方式 B：本地打包上传
# 本机执行：tar czf knoa-deploy.tar.gz --exclude=node_modules --exclude=.venv --exclude=dist --exclude=__pycache__ --exclude='.git' knoa/
# 然后通过 SCP/RDP 拖拽上传到服务器 C:\knoa\
```

### Step 6：准备 TLS 证书

#### 选项 A：过渡期自签证书（最快，浏览器会警告但能用）

在服务器上执行：

```powershell
# 生成自签证书（有效期 365 天）
cd C:\knoa
openssl req -x509 -newkey rsa:2048 `
  -keyout deploy/nginx/certs/privkey.pem `
  -out deploy/nginx/certs/fullchain.pem `
  -days 365 -nodes -subj "/CN=170.106.74.73"
```

> 如果没有 `openssl`，装一个：`choco install openssl` 或从 https://slproweb.com/products/Win32OpenSSL.html 下载。

#### 选项 B：Let's Encrypt 免费证书（需域名）

1. 先把域名（如 `knoa.yourdomain.com`）DNS A 记录指向 `170.106.74.73`
2. 用 certbot docker 方案（compose 文件已预留挂载点）：

```powershell
# 临时获取证书（一次性操作）
docker run --rm -it `
  -v C:\knoa\deploy\nginx\certbot:/var/www/certbot `
  -v C:\knoa\deploy\nginx\certs:/etc/nginx/certs `
  certbot/certbot certonly --webroot `
  -w /var/www/certbot `
  -d knoa.yourdomain.com
```

3. 证书在 `deploy/nginx/certs/` 里，nginx 会自动读取

#### 选项 C：纯 HTTP（不推荐，仅限内网测试）

如果暂时不要 HTTPS：
- `CORS_ORIGINS` 填 `http://170.106.74.73`
- 修改 `docker-compose.prod-lean.yml` 的 edge 端口映射去掉 `443:443`
- 后端 `COOKIE_SECURE` 会因非 production-like 自动关闭（但 APP_ENV=production 时仍为 True，需要在 .env 里显式设 False）

### Step 7：配置生产环境变量

```powershell
# 复制模板
copy deploy\.env.production-template deploy\.env

# 编辑填入真实值（用 notepad++ 或 VS Code）
notepad deploy\.env
```

必须修改的项：

| 变量 | 要求 | 示例 |
|------|------|------|
| `POSTGRES_PASSWORD` | 强随机，24+ hex 字符 | `a7f3c9e2b1d8...` |
| `PUBLIC_IP` | 服务器公网 IP | `170.106.74.73` |
| `CORS_ORIGINS` | 前端访问地址（须与浏览器一致） | `https://170.106.74.73` |
| `TLS_MODE` | `https` 或 `http` | `https` |

同时编辑 `backend/.env`（生产副本），确认以下值不是开发默认：

```bash
# backend/.env 中必须确认的项：
JWT_SECRET=          # 不能是 dev-change-me（当前已有强值 ✓）
ADMIN_PASSWORD=      # 不能是 admin123（当前已有强值 ✓）
APP_ENV=production   # 必须 ✓
CORS_ORIGINS=        # 必须与上面 deploy/.env 一致
DATABASE_URL=        # 不用手动改，compose environment 会覆盖
REDIS_URL=           # 不用手动改，compose environment 会覆盖
SSL_ENABLED=False    # 必须 False（TLS 由 nginx 终止）✓
```

---

## 三、启动服务

### 首次构建 + 启动

```powershell
cd C:\knoa

# 用低资源编排文件启动（前台看日志排查问题）
docker compose -f docker-compose.prod-lean.yml up --build

# 如果一切正常，Ctrl+C 后转为后台运行：
docker compose -f docker-compose.prod-lean.yml up -d --build
```

### 验证各服务状态

```powershell
# 查看容器状态（应该全部 healthy）
docker compose -f docker-compose.prod-lean.yml ps

# 查看后端日志（确认无报错、生产校验通过）
docker compose -f docker-compose.prod-lean.yml logs backend

# 测试健康检查
curl -k https://170.106.74.73/api/health       # 应返回 {"status":"ok",...}
curl -k https://170.106.74.43/                  # 应返回前端 SPA 页面
```

### 常见启动失败排查

| 现象 | 原因 | 解决 |
|------|------|------|
| backend 容器反复 restart | `validate_production_settings()` 报错 | `docker compose logs backend` 看具体哪项配置不合格 |
| postgres OOM killed | 512M 不够（数据量大时） | 升级内存或加 Windows swap |
| backend OOM killed | 768M 不够（并发高时） | 同上；或设 `UVICORN_WORKERS=1`（默认就是 1） |
| 502 Bad Gateway | backend 还没起来 | 等 30s（start_period）；`docker compose logs backend` 看进度 |
| 浏览器 CORS 报错 | CORS_ORIGINS 与实际访问地址不一致 | 检查 deploy/.env 和 browser address bar |
| 登录后立即被踢 | Cookie Secure 不匹配 | HTTP 访问时确保 COOKIE_SECURE=False |

---

## 四、首次数据初始化

### 4.1 管理员账号

首次启动时，如果数据库里没有任何用户，后端会自动用 `backend/.env` 里的 `ADMIN_USERNAME`/`ADMIN_PASSWORD` 创建管理员。当前配置会创建 `admin / 0-W-CJV_rKjPLzZdzog_hw`。

**登录后立刻改密码。**

### 4.2 数据库迁移

Alembic 迁移在 `main.py` 的 lifespan startup 里自动执行（`upgrade head`）。查看日志确认：

```powershell
docker compose -f docker-compose.prod-lean.yml logs backend | findstr alembic
# 应看到 INFO  [alembic.env] xxx → yyy...
```

### 4.3 导入种子知识库语料

```powershell
# 进入 backend 容器执行摄入脚本
docker compose -f docker-compose.prod-lean.yml exec backend python scripts/ingest_seed.py
```

这会把 `backend/scripts/seed_md/` 里的 markdown 文件解析、分块、向量化后写入 PostgreSQL。

> **注意**：向量化会调用 Embedding API（阿里云百炼），确保 `EMBEDDING_API_KEY` 正确且有余额。

### 4.4 验证检索功能

1. 浏览器打开 `https://170.106.74.73`（或 `http://` 如果选了 HTTP）
2. 用 admin 账号登录
3. 发一条测试提问："亚马逊 FBA 是什么？"
4. 应该返回带引用来源的回答（说明 RAG 管线正常）

---

## 五、运维操作

### 日常命令

```powershell
# 查看日志（跟踪所有服务）
docker compose -f docker-compose.prod-lean.yml logs -f

# 只看后端日志
docker compose -f docker-compose.prod-lean.yml logs -f backend

# 重启某个服务（改了配置后）
docker compose -f docker-compose.prod-lean.yml restart backend

# 全量重建（代码更新后）
docker compose -f docker-compose.prod-lean.yml up -d --build

# 停止所有服务
docker compose -f docker-compose.prod-lean.yml down

# 停止并删除数据卷（⚠️ 会丢数据！仅迁移/重置时用）
docker compose -f docker-compose.prod-lean.yml down -v
```

### 备份（手动触发）

```powershell
# 执行一次备份（--rm 执行完自动删除容器，不占常驻内存）
docker compose -f docker-compose.prod-lean.yml --profile backup run --rm backup

# 备份文件在 Docker 卷 knoa_backups 里，导出到宿主机：
docker cp knoa-backup:/backups C:\knoa-backups\
```

设置 Windows 计划任务每日自动备份（可选）：

```powershell
# 创建定时备份脚本 C:\knoa\backup-daily.bat
@echo off
cd /d C:\knoa
docker compose -f docker-compose.prod-lean.yml --profile backup run --rm backup

# 然后在「任务计划程序」中添加每天凌晨 3 点执行此 bat
```

### 更新代码

```powershell
cd C:\knoa
git pull origin master
docker compose -f docker-compose.prod-lean.yml up -d --build
```

---

## 六、安全基线检查清单

- [ ] **防火墙**：只开放 80/443（+ 22 SSH 限来源 IP）
- [ ] **腾讯云安全组**：入站规则仅放行 TCP 80/443/22
- [ ] **Windows 远程桌面**：改默认端口 3389 → 高位端口 / 或禁用 RDP 只用 SSH
- [ ] **管理员密码**：已改为强密码（非初始密码）
- [ ] **Docker**：不用 root 运行容器（Dockerfile 已用 appuser ✓）
- [ ] **TLS**：启用 HTTPS（即使自签也比明文强）
- [ ] **生产密钥**：所有 change-me 默认值已替换
- [ ] **API Docs**：生产环境自动关闭 `/docs` `/redoc`（APP_ENV=production ✓）
- [ ] **CORS**：不用通配符 `*`（已配具体 IP/域名 ✓）

---

## 七、迁移到阿里云预案

当过渡期结束、准备迁移到阿里云时：

### 7.1 阿里云服务器选型建议

| 配置 | 用途 | 参考价格 |
|------|------|---------|
| 2C4G | 最低可用（比现在多 2G 内存缓冲） | ~100-150 元/月 |
| 2C8G | 推荐（Docker 原始配置可直跑） | ~200-250 元/月 |
| 4C8G | 生产推荐（有余量应对流量波峰） | ~350-400 元/月 |

OS 建议：**Ubuntu 22.04 / 24.04 LTS**（Docker 原生支持更好，没有 Hyper-V 开销，同等配置下可用内存多 ~500MB）。

### 7.2 迁移步骤

```bash
# 1. 新服务器装 Docker（Linux 比 Windows 轻得多）
curl -fsSL https://get.docker.com | sh

# 2. 同样 clone 代码、复制 deploy/.env、更新 PUBLIC_IP/CORS_ORIGINS

# 3. 从腾讯云导出数据卷
# 腾讯云服务器上：
docker run --rm -v knoa_pgdata:/data -v $(pwd):/backup alpine tar czf /backup/pgdata.tar.gz -C /data .
docker run --rm -v knoa_uploads:/data -v $(pwd):/backup alpine tar czf /backup/uploads.tar.gz -C /data .
docker run --rm -v knoa_redisdata:/data -v $(pwd):/backup alpine tar czf /backup/redisdata.tar.gz -C /data .

# 4. SCP 传到阿里云

# 5. 阿里云上导入数据卷（先 docker compose up -d 创建空卷）
docker run --rm -v knoa_pgdata:/data -v $(pwd):/backup alpine sh -c "tar xzf /backup/pgdata.tar.gz -C /data"
docker run --rm -v knoa_uploads:/data -v $(pwd):/backup alpine sh -c "tar xzf /backup/uploads.tar.gz -C /data"

# 6. 如果阿里云 ≥ 4G 内存，切回原始 compose 文件：
docker compose -f docker-compose.yml up -d --build

# 7. DNS 切换（如果有域名）：A 记录指向新 IP
```

### 7.3 迁移时的配置差异

| 项目 | 腾讯云（当前） | 阿里云（目标） |
|------|--------------|---------------|
| 编排文件 | `docker-compose.prod-lean.yml`（裁剪版） | `docker-compose.yml`（完整版） |
| OS | Windows Server 2016 | Ubuntu 22.04/24.04 LTS |
| Docker | Docker Desktop + Hyper-V | Docker Engine（原生 Linux） |
| 可用内存 | ~1GB 给容器 | ~3.5GB 给容器（4G 机器） |
| 备份 | 手动/Windows 计划任务 | docker cron 或 systemd timer |
| 防火墙 | Windows Firewall + 安全组 | ufw + 安全组 |

---

## 八、快速参考卡

```powershell
# ═══ 启停 ═══
docker compose -f docker-compose.prod-lean.yml up -d --build    # 构建+启动
docker compose -f docker-compose.prod-lean.yml down              # 停止
docker compose -f docker-compose.prod-lean.yml logs -f backend   # 看后端日志

# ═══ 备份 ═══
docker compose -f docker-compose.prod-lean.yml --profile backup run --rm backup

# ═══ 数据库进入（调试用）═══
docker compose -f docker-compose.prod-lean.yml exec postgres psql -U knoa -d knoa

# ═══ 后端 shell（调试用）═══
docker compose -f docker-compose.prod-lean.yml exec backend sh

# ═══ 资源监控 ═══
docker stats                                                   # 实时内存/CPU
```
