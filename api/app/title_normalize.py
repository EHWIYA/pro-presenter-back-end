"""곡 제목 정규화 — cursor-llm-gateway title-normalize.ts 와 동일 규칙."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"[\s\u00a0]+")


def normalize_song_title(title: str | None) -> str:
    if not title:
        return ""
    s = unicodedata.normalize("NFKC", title).casefold()
    s = _WHITESPACE.sub("", s)
    return "".join(ch for ch in s if ch.isalnum())
