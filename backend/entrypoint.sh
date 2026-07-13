#!/bin/sh
# Knoa backend 容器启动脚本
# - SSL_ENABLED=True 且证书缺失时，临时生成自签证书（仅容器本地用）
# - 否则以明文 HTTP 启动（compose 内部走明文，TLS 由宿主机反代终止）
set -e

cd /app

if [ "${SSL_ENABLED}" = "True" ] || [ "${SSL_ENABLED}" = "true" ]; then
  if [ ! -f "${SSL_KEY_FILE}" ] || [ ! -f "${SSL_CERT_FILE}" ]; then
    echo "[entrypoint] SSL_ENABLED=True 但证书缺失，生成临时自签证书"
    mkdir -p "$(dirname "${SSL_KEY_FILE}")" "$(dirname "${SSL_CERT_FILE}")"
    openssl req -x509 -newkey rsa:2048 \
      -keyout "${SSL_KEY_FILE}" -out "${SSL_CERT_FILE}" \
      -days 365 -nodes -subj "/CN=localhost"
  fi
  echo "[entrypoint] 以 HTTPS 启动 uvicorn :8000"
  exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    --ssl-keyfile "${SSL_KEY_FILE}" --ssl-certfile "${SSL_CERT_FILE}"
else
  echo "[entrypoint] 以 HTTP 启动 uvicorn :8000"
  exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
