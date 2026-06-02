#!/usr/bin/env bash
# 개발 PC → NAS 로 api/ 운영 파일만 전송 (bin·compose 변경 시)
# 사용: NAS_SSH=iwh@100.x.x.x NAS_DEPLOY_PATH=/home/iwh/pro-presenter/api ./bin/install-live-remote.sh
set -euo pipefail

REPO_OPS="$(cd "$(dirname "$0")/.." && pwd)"
SSH_TARGET="${NAS_SSH:?NAS_SSH 필요 — 예: iwh@100.99.47.84}"
DEPLOY_ROOT="${NAS_DEPLOY_PATH:-/home/iwh/pro-presenter/api}"
REMOTE="${DEPLOY_ROOT}"

rsync -avz \
  "${REPO_OPS}/docker-compose.yml" \
  "${REPO_OPS}/venues.json" \
  "${REPO_OPS}/bin/" \
  "${SSH_TARGET}:${REMOTE}/"
# .env 는 NAS에만 두고 덮어쓰지 않음

ssh "$SSH_TARGET" "chmod +x ${REMOTE}/bin/*.sh; ${REMOTE}/bin/setup-nas.sh"
echo "install: ${REMOTE} 반영 완료"
