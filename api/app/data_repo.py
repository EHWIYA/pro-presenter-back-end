"""pro-presenter-data 마운트 경로 · git revision."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings

LIBRARIES_DIRNAME = "Libraries"


def resolve_data_repo_path(settings: Settings) -> Path:
    return settings.resolved_data_repo_path


def libraries_root(settings: Settings) -> Path:
    return resolve_data_repo_path(settings) / LIBRARIES_DIRNAME


def read_git_revision(repo_path: Path) -> str | None:
    if not (repo_path / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    revision = (result.stdout or "").strip()
    return revision or None


def file_mtime_iso(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
    except OSError:
        return datetime.now(UTC).isoformat()
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()
