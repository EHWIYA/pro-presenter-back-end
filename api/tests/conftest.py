"""pytest 공통 환경 (로컬·GHA 동일). main import 전에 경로를 고정한다."""

from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_API_ROOT = Path(__file__).resolve().parents[1]

os.environ["VENUES_JSON_PATH"] = str(_REPO_ROOT / "live" / "venues.json")
os.environ["BIBLE_JSON_PATH"] = str(_API_ROOT / "data" / "bible-krv.sample.json")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
