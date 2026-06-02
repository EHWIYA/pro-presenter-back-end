#!/usr/bin/env bash
# NAS 1회 준비 — 디렉터리·예시 설정 (repo clone 불필요)
set -euo pipefail

OPS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$OPS_DIR"

mkdir -p data bin
chmod +x bin/*.sh 2>/dev/null || true

if [ ! -f .env ]; then
  echo "setup: ops/.env 없음 — docs/ENV.md 참고 후 생성하세요" >&2
  exit 1
fi

[ -f venues.json ] || echo "setup: venues.json 을 배치하세요"
[ -f data/bible-krv.json ] || echo "setup: data/bible-krv.json (전체 성경) 을 배치하세요"

echo "setup: 완료 (${OPS_DIR})"
