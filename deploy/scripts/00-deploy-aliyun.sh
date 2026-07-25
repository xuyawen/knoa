#!/usr/bin/env bash
# ============================================================================
# Knoa 一键部署脚本 —— 阿里云 Linux 3 (RHEL8 兼容) · 2C2G 过渡期
#
# 用法（在服务器上，root 身份）：
#   bash 00-deploy-aliyun.sh <公网IP>
#   例：bash 00-deploy-aliyun.sh 8.134.14.177
#
# 做的事：
#   1. 用阿里云镜像源装 Docker CE + compose v2（国内快）
#   2. 配置国内 Docker 镜像加速（daocloud 公共源）
#   3. 克隆代码（github 不通时自动走 ghproxy 镜像）
#   4. 生成根目录 .env（随机 PG 口令、HTTP 模式、CORS=http://IP）
#   5. 用 HTTP 版 nginx 配置覆盖 edge 挂载的 nginx.conf
#   6. 给 backend/.env 补 COOKIE_SECURE=False（HTTP 下登录必需）
#   7. 构建并后台启动全部服务 + 健康检查
#
# 注意：本脚本只覆盖「过渡期纯 IP + HTTP」场景。上域名后请改回
#       deploy/nginx/nginx.conf（HTTPS 版）+ 申请证书 + TLS_MODE=https。
# ============================================================================

set -uo pipefail

PUBLIC_IP="${1:-}"
if [[ -z "$PUBLIC_IP" ]]; then
  echo "✗ 用法: bash $0 <公网IP>" >&2
  exit 1
fi

REPO_DIR="/opt/knoa"
run() { echo -e "\n\033[36m==> $*\033[0m"; }

# ---------------------------------------------------------------------------
run "[1/7] 安装 Docker CE（阿里云镜像源，强制 el8 包）"
if ! command -v docker >/dev/null 2>&1; then
  yum install -y yum-utils >/dev/null 2>&1
  yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
  # 阿里云 Linux 3 的 $releasever 是 3，docker-ce 仓只有 el8/el9，强制改成 8
  sed -i 's/\$releasever/8/g' /etc/yum.repos.d/docker-ce.repo
  yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
else
  echo "    docker 已安装，跳过"
fi
docker --version
docker compose version

# ---------------------------------------------------------------------------
run "[2/7] 配置 Docker 国内镜像加速"
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": ["https://docker.m.daocloud.io"]
}
EOF
systemctl restart docker
echo "    （可选）若你有阿里云容器镜像加速器地址，可加到上面数组里提速"
docker info | grep -A1 "Registry Mirrors"

# ---------------------------------------------------------------------------
run "[3/7] 克隆代码（github 失败自动走 ghproxy）"
yum install -y git >/dev/null 2>&1
if [[ ! -d "$REPO_DIR" ]]; then
  cd /opt
  git clone --depth 1 https://github.com/xuyawen/knoa.git knoa || \
  git clone --depth 1 https://ghproxy.com/https://github.com/xuyawen/knoa.git knoa
fi
cd "$REPO_DIR"
git log --oneline -1

# ---------------------------------------------------------------------------
run "[4/7] 生成根目录 .env（随机 PG 口令 + HTTP 模式）"
cp deploy/.env.production-template .env
PGPASS=$(openssl rand -hex 24)
sed -i "s|^PUBLIC_IP=.*|PUBLIC_IP=${PUBLIC_IP}|" .env
sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=http://${PUBLIC_IP}|" .env
sed -i "s|^TLS_MODE=.*|TLS_MODE=http|" .env
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PGPASS}|" .env
echo "    PG 口令已随机生成（记一下，重置用）: ${PGPASS}"

# ---------------------------------------------------------------------------
run "[5/7] 用 HTTP 版 nginx 覆盖 edge 挂载的 nginx.conf + 建证书目录"
cp deploy/nginx/nginx.http.conf deploy/nginx/nginx.conf
mkdir -p deploy/nginx/certs deploy/nginx/certbot

# ---------------------------------------------------------------------------
run "[6/7] backend/.env 补 COOKIE_SECURE=False（HTTP 下登录必需）"
if ! grep -q '^COOKIE_SECURE' backend/.env; then
  echo "COOKIE_SECURE=False" >> backend/.env
fi
# 顺手让 npm 构建走国内镜像（仅服务器本地文件，不进 git 也行）
echo "registry=https://registry.npmmirror.com" > frontend/.npmrc

# ---------------------------------------------------------------------------
run "[7/7] 构建并后台启动（首次构建需几分钟，请耐心等）"
docker compose -f docker-compose.prod-lean.yml up -d --build

echo -e "\n\033[33m==> 等待 35s 让服务起来...\033[0m"
sleep 35
docker compose -f docker-compose.prod-lean.yml ps

echo -e "\n\033[36m==> 健康检查\033[0m"
if curl -fsS "http://localhost/api/health"; then
  echo -e "\n\033[32m✓ 后端健康检查通过\033[0m"
else
  echo -e "\n\033[31m✗ 后端健康检查失败，看日志: docker compose -f docker-compose.prod-lean.yml logs backend\033[0m"
fi

echo -e "\n\033[32m========================================================"
echo " 部署完成！"
echo " 访问: http://${PUBLIC_IP}"
echo " 登录: admin / 0-W-CJV_rKjPLzZdzog_hw   （登录后立刻改密码）"
echo " 查看日志: docker compose -f docker-compose.prod-lean.yml logs -f backend"
echo "========================================================\033[0m"
