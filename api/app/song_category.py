"""곡 category 값 검증·slug 생성·기본값."""

from __future__ import annotations

import re

_BUILTIN_CATEGORIES = frozenset({"praise", "hymn", "special"})
BUILTIN_CATEGORY_IDS = ("praise", "hymn", "special")
BUILTIN_CATEGORY_LABELS: dict[str, str] = {
    "praise": "찬양",
    "hymn": "성가곡",
    "special": "특송",
}
_BUILTIN_LABELS_LOWER = frozenset(v.lower() for v in BUILTIN_CATEGORY_LABELS.values())
_CUSTOM_PREFIX = "custom:"
_CUSTOM_SLUG_RE = re.compile(r"^[\w가-힣\-]+$", re.UNICODE)
_SLUG_CHAR_RE = re.compile(r"[\w가-힣\-]", re.UNICODE)
_MAX_LABEL_LEN = 24
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


def is_builtin_category_id(category_id: str) -> bool:
    return category_id in _BUILTIN_CATEGORIES


def validate_category_label(label: str) -> str:
    """카테고리 마스터 라벨 검증. 정규화된 라벨 반환."""
    trimmed = label.strip()
    if not trimmed:
        raise SongCategoryError("label이 비어 있습니다.")
    if len(trimmed) > _MAX_LABEL_LEN:
        raise SongCategoryError(f"label은 최대 {_MAX_LABEL_LEN}자입니다.")
    if trimmed.lower() in _BUILTIN_LABELS_LOWER:
        raise SongCategoryError("기본 카테고리와 동일한 라벨은 사용할 수 없습니다.")
    return trimmed


def slugify_category_label(label: str) -> str:
    """프론트 slugifyCategoryLabel과 동일: 공백→하이픈, 허용 문자만 유지."""
    trimmed = label.strip()
    slug = re.sub(r"\s+", "-", trimmed)
    slug = "".join(_SLUG_CHAR_RE.findall(slug))
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def make_custom_category_id(label: str) -> str:
    """라벨 → custom:<slug> ID. slug 불가 시 SongCategoryError."""
    normalized = validate_category_label(label)
    slug = slugify_category_label(normalized)
    if not slug or not _CUSTOM_SLUG_RE.fullmatch(slug):
        raise SongCategoryError("label에서 유효한 slug를 생성할 수 없습니다.")
    return f"{_CUSTOM_PREFIX}{slug}"
