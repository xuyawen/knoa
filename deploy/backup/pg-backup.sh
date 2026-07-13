#!/bin/sh
# Knoa Postgres 每日备份：pg_dump -> gzip -> 时间戳文件，并清理过期备份。
# 由 docker-compose.yml 的 backup 服务每 24h 调用一次（see command: while true; do ...; sleep 86400）。
#
# 连接参数来自环境变量（compose 里注入）：
#   PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE
#   BACKUP_DIR           落盘目录（默认 /backups，挂载 knoa_backups 卷）
#   BACKUP_RETENTION_DAYS 保留天数（默认 7，超过则 find -mtime 删除）
set -e

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION="${BACKUP_RETENTION_DAYS:-7}"
DATE="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/knoa_${DATE}.sql.gz"

echo "[backup] dumping ${PGDATABASE}@${PGHOST}:${PGPORT:-5432} -> ${OUT}"
# --no-owner/--no-privileges 让恢复时不依赖原角色；gzip 流式压缩
pg_dump --format=plain --no-owner --no-privileges "${PGDATABASE}" \
  | gzip > "${OUT}.tmp"
mv "${OUT}.tmp" "${OUT}"

echo "[backup] removing backups older than ${RETENTION} days"
find "${BACKUP_DIR}" -maxdepth 1 -name 'knoa_*.sql.gz' -mtime "+${RETENTION}" -delete

echo "[backup] done. current backups:"
ls -1t "${BACKUP_DIR}"/knoa_*.sql.gz 2>/dev/null | sed 's/^/  /' || echo "  (none)"
