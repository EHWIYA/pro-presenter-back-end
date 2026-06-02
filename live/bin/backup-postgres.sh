#!/usr/bin/env bash
# pro-presenter Postgres 백업 (iot backup-iot-postgresql.sh 패턴)
set -euo pipefail

LIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${LIVE_DIR}/.env.postgres"
BACKUP_DIR="${HOME}/backup/pro-presenter-postgres"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/pp_db_${STAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

PP_POSTGRES_DB="${PP_POSTGRES_DB:-pp_db}"
PP_POSTGRES_USER="${PP_POSTGRES_USER:-pp_user}"

docker exec pro-presenter-postgres \
  pg_dump -U "$PP_POSTGRES_USER" -d "$PP_POSTGRES_DB" --no-owner --no-acl \
  | gzip > "$OUT"

echo "backup: $OUT"
find "$BACKUP_DIR" -name 'pp_db_*.sql.gz' -mtime +14 -delete
