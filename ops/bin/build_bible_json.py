#!/usr/bin/env python3
"""NAS용 성경 JSON 변환 (api 패키지 불필요). fetch-bible-krv.sh 에서 호출."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BOOK_CANON_ORDER = [
    "genesis", "exodus", "leviticus", "numbers", "deuteronomy", "joshua", "judges", "ruth",
    "1samuel", "2samuel", "1kings", "2kings", "1chronicles", "2chronicles", "ezra", "nehemiah",
    "esther", "job", "psalms", "proverbs", "ecclesiastes", "songofsongs", "isaiah", "jeremiah",
    "lamentations", "ezekiel", "daniel", "hosea", "joel", "amos", "obadiah", "jonah", "micah",
    "nahum", "habakkuk", "zephaniah", "haggai", "zechariah", "malachi", "matthew", "mark", "luke",
    "john", "acts", "romans", "1corinthians", "2corinthians", "galatians", "ephesians",
    "philippians", "colossians", "1thessalonians", "2thessalonians", "1timothy", "2timothy",
    "titus", "philemon", "hebrews", "james", "1peter", "2peter", "1john", "2john", "3john",
    "jude", "revelation",
]

_ALIAS_TO_KEY = {
    "창세기": "genesis", "창": "genesis", "요한복음": "john", "요": "john",
    "로마서": "romans", "롬": "romans",
}


_VERSE_QUOTE_CHARS = '"\'\u201c\u201d\u2018\u2019'
TRANSLATION_KRV = "개역개정"


def normalize_verse_text(text: str) -> str:
    cleaned = text.strip()
    for ch in _VERSE_QUOTE_CHARS:
        cleaned = cleaned.replace(ch, "")
    return cleaned


def _book_key(name: str, index: int) -> str | None:
    name = name.strip()
    if name in _ALIAS_TO_KEY:
        return _ALIAS_TO_KEY[name]
    if index < len(BOOK_CANON_ORDER):
        return BOOK_CANON_ORDER[index]
    return None


def convert(raw: list[Any]) -> dict[str, Any]:
    books: dict[str, Any] = {}
    for i, book in enumerate(raw):
        if not isinstance(book, dict):
            continue
        key = _book_key(str(book.get("name") or book.get("abbrev") or ""), i)
        if not key:
            continue
        chapters: dict[str, dict[str, str]] = {}
        for ch_idx, verses in enumerate(book.get("chapters", []), start=1):
            if not isinstance(verses, list):
                continue
            ch_map = {
                str(vi): normalize_verse_text(str(t))
                for vi, t in enumerate(verses, 1)
                if t
            }
            if ch_map:
                chapters[str(ch_idx)] = ch_map
        books[key] = {"name": str(book.get("name") or key), "chapters": chapters}
    return {"translation": TRANSLATION_KRV, "books": books}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("-i", "--input", type=Path, required=True)
    p.add_argument("-o", "--output", type=Path, required=True)
    args = p.parse_args()
    with args.input.open(encoding="utf-8-sig") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        print("array JSON 만 지원", file=sys.stderr)
        return 1
    out = convert(raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    n = sum(len(v) for b in out["books"].values() for v in b["chapters"].values())
    print(f"OK {args.output} ({len(out['books'])} books, {n} verses)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
