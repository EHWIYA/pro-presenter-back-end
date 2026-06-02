#!/usr/bin/env bash
# NAS 배포 — pull + 재시작 + health (GHA·수동 공용)
# 사용: ./bin/deploy.sh ghcr.io/OWNER/REPO:main
set -euo pipefail

OPS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$OPS_DIR"

IMAGE="${1:?이미지 필요 — 예: ghcr.io/owner/repo:main}"
ENV_FILE="${OPS_DIR}/.env"

die() { echo "deploy: $*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || die ".env 없음 — docs/ENV.md 참고 후 ops/.env 생성"
[ -f venues.json ] || die "venues.json 없음"

if grep -q '^GHCR_TOKEN=' "$ENV_FILE" 2>/dev/null; then
  GHCR_USER="$(grep -m1 '^GHCR_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' || true)"
  GHCR_TOKEN="$(grep -m1 '^GHCR_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '"')"
  echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER:-${USER}}" --password-stdin >/dev/null
fi

if grep -q '^PP_API_IMAGE=' "$ENV_FILE"; then
  sed -i "s|^PP_API_IMAGE=.*|PP_API_IMAGE=${IMAGE}|" "$ENV_FILE"
else
  echo "PP_API_IMAGE=${IMAGE}" >>"$ENV_FILE"
fi
export PP_API_IMAGE="$IMAGE"

echo "deploy: pull ${IMAGE}"
docker compose pull -q
docker compose up -d --remove-orphans

if docker compose ps --status running pro-presenter-api >/dev/null 2>&1; then
  echo "deploy: alembic upgrade head"
  docker compose exec -T pro-presenter-api alembic upgrade head || die "alembic migrate 실패"
fi

for i in 1 2 3; do
  if curl -sf http://127.0.0.1:8003/health >/dev/null; then
    echo "deploy: health OK"
    docker compose ps
    exit 0
  fi
  sleep 2
done

die "health check 실패 (127.0.0.1:8003/health)"
