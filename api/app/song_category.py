"""곡 category 값 검증·기본값."""

from __future__ import annotations

import re

_BUILTIN_CATEGORIES = frozenset({"praise", "hymn", "special"})
_CUSTOM_PREFIX = "custom:"
_CUSTOM_SLUG_RE = re.compile(r"^[\w가-힣\-]+$", re.UNICODE)
DEFAULT_CATEGORY = "praise"


class SongCategoryError(ValueError):
    pass


def normalize_category(value: str | None) -> str:
    """생략·빈 문자열 → praise, 그 외는 validate_category."""
    if value is None or not str(value).strip():
        return DEFAULT_CATEGORY
    return validate_category(str(value).strip())


def validate_category(value: str) -> str:
    if value in _BUILTIN_CATEGORIES:
        return value
    if value.startswith(_CUSTOM_PREFIX):
        slug = value[len(_CUSTOM_PREFIX) :]
        if slug and _CUSTOM_SLUG_RE.fullmatch(slug):
            return value
    raise SongCategoryError(
        "category는 praise, hymn, special 또는 custom:<slug> 형식이어야 합니다."
    )
