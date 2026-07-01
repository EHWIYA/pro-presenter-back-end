"""에이전트 Libraries/<카테고리>/<파일>.pro 경로 규칙."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from app.song_category import DEFAULT_CATEGORY

KST = timezone(timedelta(hours=9))

SCRIPTURE_LIBRARY_CATEGORY = "말씀"
SONG_LIBRARY_CATEGORIES = frozenset({"찬양", "찬송가", "성가곡"})

_HYMNAL_TITLE_RE = re.compile(r"^\d+\.")
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00]')


class AgentLibraryError(ValueError):
    pass


def kst_today() -> date:
    return datetime.now(KST).date()


def normalize_presentation_filename(name: str) -> str:
    """`.pro` 접미사 보장, 경로·금지 문자 제거."""
    trimmed = name.strip()
    if not trimmed:
        raise AgentLibraryError("presentation_filename이 비어 있습니다.")
    base = trimmed.replace("\\", "/").split("/")[-1]
    if _INVALID_FILENAME_CHARS.search(base):
        raise AgentLibraryError("presentation_filename에 사용할 수 없는 문자가 있습니다.")
    if not base.lower().endswith(".pro"):
        base = f"{base}.pro"
    return base


def default_scripture_presentation_filename(*, service_date: date | None = None) -> str:
    """말씀 기본 파일명: YYMMDD-말씀.pro"""
    d = service_date or kst_today()
    return f"{d:%y%m%d}-말씀.pro"


def resolve_scripture_presentation_filename(value: str | None) -> str:
    if value and value.strip():
        return normalize_presentation_filename(value)
    return default_scripture_presentation_filename()


def resolve_scripture_library_category(
    value: str | None,
    *,
    default: str = SCRIPTURE_LIBRARY_CATEGORY,
) -> str:
    if value and value.strip():
        return value.strip()
    return default


def song_category_to_library_category(category_id: str | None) -> str:
    cat = (category_id or DEFAULT_CATEGORY).strip()
    if cat == "hymn":
        return "성가곡"
    if cat == "hymnal":
        return "찬송가"
    if cat == "special":
        return "찬양"
    return "찬양"


def resolve_song_library_category(
    *,
    song_title: str,
    song_category: str | None = None,
    override: str | None = None,
) -> str:
    """곡 메타·제목 패턴 → agent library_category."""
    if override and override.strip():
        category = override.strip()
        if category not in SONG_LIBRARY_CATEGORIES:
            raise AgentLibraryError(
                f"library_category는 {', '.join(sorted(SONG_LIBRARY_CATEGORIES))} 중 하나여야 합니다."
            )
        return category
    if _HYMNAL_TITLE_RE.match(song_title.strip()):
        return "찬송가"
    return song_category_to_library_category(song_category)
