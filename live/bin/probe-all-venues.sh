#!/usr/bin/env bash
set -euo pipefail
API_BASE="${API_BASE:-http://127.0.0.1:8003}"
LIVE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENUES_JSON="${VENUES_JSON:-${LIVE_DIR}/venues.json}"

for id in $(python3 -c "
import json, sys
p=sys.argv[1]
with open(p, encoding='utf-8') as f:
    for v in json.load(f).get('venues', []):
        if v.get('enabled', True):
            print(v['id'])
" "$VENUES_JSON"); do
  echo "=== $id ==="
  API_BASE="$API_BASE" "$(dirname "$0")/probe-venue.sh" "$id"
  echo
done
