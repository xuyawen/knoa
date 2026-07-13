#!/bin/sh
# 生成自签 TLS 证书到 deploy/nginx/certs/（仅用于本地/测试，浏览器会报不安全）。
# 生产请改用 Let's Encrypt（certbot）或你自己的证书，把 fullchain.pem / privkey.pem
# 放到同一目录即可，本脚本无需运行。
set -e

DIR="$(cd "$(dirname "$0")" && pwd)/certs"
mkdir -p "$DIR"
KEY="$DIR/privkey.pem"
CERT="$DIR/fullchain.pem"

if [ -f "$KEY" ] && [ -f "$CERT" ]; then
  echo "[selfsigned] 证书已存在，跳过：$KEY / $CERT"
  exit 0
fi

echo "[selfsigned] 生成自签证书 -> $DIR"
openssl req -x509 -newkey rsa:2048 \
  -keyout "$KEY" -out "$CERT" \
  -days 365 -nodes -subj "/CN=localhost"

echo "[selfsigned] 完成。生产环境请替换为真实证书（同名覆盖即可）。"
