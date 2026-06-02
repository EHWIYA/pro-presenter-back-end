#!/usr/bin/env bash
# 사용: probe-venue.sh <venue_id>
set -euo pipefail
API_BASE="${API_BASE:-http://127.0.0.1:8003}"
VID="${1:?venue_id 필요}"
exec curl -sS "${API_BASE}/venues/${VID}/probe" | python3 -m json.tool
