# Knoa Edge 反向代理（TLS 终止）

由 `docker-compose.yml` 的 `edge` 服务运行 `nginx:alpine`，配置文件即本目录的
`nginx.conf`（挂载到容器内 `/etc/nginx/conf.d/default.conf`）。它负责：

- **TLS 终止**：对外只暴露 80/443，443 上做 HTTPS，80 一律 301 跳 https。
- **路由**：
  - `/`         → `frontend:80`（SPA 静态资源，由前端 nginx 托管）
  - `/api/`     → `backend:8000`（**流式问答 SSE 必须关闭代理缓冲**）
- **安全头**：HSTS、X-Content-Type-Options、X-Frame-Options、Referrer-Policy。
- **TLS 加固**：仅 TLS1.2/1.3，关闭 session ticket。

> 后端 `backend` 在容器内跑明文 HTTP（`SSL_ENABLED=False`），TLS 全部交给 edge。
> 证书私钥**只存在于宿主机 `deploy/nginx/certs/`**，绝不进镜像或 git（见根 `.gitignore`）。

---

## 1. 准备证书

证书放在宿主机 `deploy/nginx/certs/`，文件名固定：

```
deploy/nginx/certs/fullchain.pem
deploy/nginx/certs/privkey.pem
```

### 选项 A：自签（本地 / 测试）

```bash
cd deploy/nginx
bash generate-selfsigned.sh          # 生成 deploy/nginx/certs/{privkey,fullchain}.pem
```

浏览器会提示「不安全」，本地测试忽略即可。

### 选项 B：Let's Encrypt（生产推荐）

```bash
# 用 certbot 申请（以 example.com 为例，先确认 DNS 已指向本机 80 端口）
sudo certbot certonly --webroot -w deploy/nginx/certbot -d knoa.example.com

# 把签发的证书软链/复制成约定文件名
cp /etc/letsencrypt/live/knoa.example.com/fullchain.pem deploy/nginx/certs/fullchain.pem
cp /etc/letsencrypt/live/knoa.example.com/privkey.pem   deploy/nginx/certs/privkey.pem
```

nginx.conf 里已为 `certbot` 的 http-01 挑战预留了
`location /.well-known/acme-challenge/`，指向挂载的 `deploy/nginx/certbot`。

> 若用 certbot，建议加个 systemd timer / cron 定期 `certbot renew`，
> 续期后新证书自动被 bind mount 读取，**无需重建 edge 容器**（nginx 重载即可：
> `docker compose exec edge nginx -s reload`）。

---

## 2. 启动

```bash
# 生产（含 edge + 每日备份）
docker compose up -d --build

# 验证
curl -kI https://localhost/api/health     # 应 200，且响应头带 Strict-Transport-Security
docker compose ps                          # knoa-edge / knoa-backend / knoa-frontend 均 Up
```

---

## 3. 常见问题

- **edge 起不来 / 一直 restart**：多半是 `deploy/nginx/certs/` 里缺证书，
  nginx 因 `ssl_certificate` 找不到文件而退出。先放好证书再 `up`。
- **SSE 回答被攒批、一次性吐出**：确认 `nginx.conf` 的 `location /api/` 里
  `proxy_buffering off;` 生效（改完 `docker compose exec edge nginx -s reload`）。
- **CORS 报错**：`docker-compose.yml` 里 `backend` 的 `CORS_ORIGINS`
  必须包含你访问站点的 Origin（如 `https://knoa.example.com`）。
- **换证书不生效**：`docker compose exec edge nginx -s reload` 即可热加载，
  不必重建容器。
