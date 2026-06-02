#!/usr/bin/env bash
# 로컬 api/data/bible-krv.json → NAS <repo>/ops/data/ (scp)
# 사용: NAS_SSH=iwh@100.88.40.125 ./bin/copy-bible-to-nas.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="${REPO_ROOT}/api/data/bible-krv.json"
SSH_TARGET="${NAS_SSH:?NAS_SSH 필요}"
DEPLOY_ROOT="${NAS_DEPLOY_PATH:-/home/iwh/pro-presenter/api}"
REMOTE="${DEPLOY_ROOT}/ops"

[ -f "$SRC" ] || {
  echo "없음: $SRC — api/scripts/build_bible_json.py 로 먼저 생성하세요." >&2
  exit 1
}

scp "$SRC" "${SSH_TARGET}:${REMOTE}/data/bible-krv.json"
echo "OK → ${SSH_TARGET}:${REMOTE}/data/bible-krv.json"
