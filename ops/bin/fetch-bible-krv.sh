#!/usr/bin/env bash
# NAS에서 개역개정(한국어) JSON 다운로드·변환 — api 레포 없이 동작
# 필요: python3, curl
# 사용: ./bin/fetch-bible-krv.sh
set -euo pipefail

LIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${LIVE_DIR}/data/bible-krv.json"
SRC_URL="${BIBLE_SRC_URL:-https://raw.githubusercontent.com/thiagobodruk/bible/master/json/ko_ko.json}"
BUILD_SCRIPT="${LIVE_DIR}/bin/build_bible_json.py"

if [ ! -f "$BUILD_SCRIPT" ]; then
  echo "fetch-bible: ${BUILD_SCRIPT} 없음 — install-live-remote.sh 로 bin/ 동기화하세요." >&2
  exit 1
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

echo "fetch-bible: download"
curl -fsSL "$SRC_URL" -o "$TMP"
mkdir -p "${LIVE_DIR}/data"
echo "fetch-bible: convert → ${OUT}"
python3 "$BUILD_SCRIPT" -i "$TMP" -o "$OUT"
echo "fetch-bible: done ($(wc -c <"$OUT") bytes)"
