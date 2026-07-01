#!/usr/bin/env bash
# pro-presenter-data 정본 동기화 — BFF 곡 카탈로그 (pytest fixture 사용 금지)
# 사용: ./bin/sync-data-repo.sh
set -euo pipefail

OPS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${OPS_DIR}/data/pro-presenter-data"
REPO_URL="${DATA_REPO_GIT_URL:-https://github.com/EHWIYA/pro-presenter-data.git}"

die() { echo "sync-data-repo: $*" >&2; exit 1; }

_fixture_warning() {
  if [ -f "${DATA_DIR}/Libraries/찬양/테스트곡.pro" ] \
    && [ -f "${DATA_DIR}/Libraries/찬양/주님의 마음.pro" ] \
    && [ ! -d "${DATA_DIR}/.git" ]; then
    die "pytest fixture 디렉터리로 보입니다. ${DATA_DIR} 를 제거한 뒤 다시 실행하세요."
  fi
}

mkdir -p "${OPS_DIR}/data"

if [ -d "${DATA_DIR}/.git" ]; then
  echo "sync-data-repo: git pull ${DATA_DIR}"
  git -C "${DATA_DIR}" fetch --depth 1 origin main
  git -C "${DATA_DIR}" pull --ff-only origin main
else
  _fixture_warning
  if [ -d "${DATA_DIR}" ]; then
    backup="${DATA_DIR}.bak.$(date +%Y%m%d%H%M%S)"
    echo "sync-data-repo: 기존 비-git 디렉터리 → ${backup}"
    mv "${DATA_DIR}" "${backup}"
  fi
  echo "sync-data-repo: clone ${REPO_URL}"
  git clone --depth 1 --branch main "${REPO_URL}" "${DATA_DIR}"
fi

count="$(find "${DATA_DIR}/Libraries" -name '*.pro' 2>/dev/null | wc -l | tr -d ' ')"
revision="$(git -C "${DATA_DIR}" rev-parse --short HEAD 2>/dev/null || echo '?')"
echo "sync-data-repo: OK revision=${revision} pro_files=${count}"
