#!/usr/bin/env python3
"""외부 성경 JSON → pro-presenter bible-krv.json 변환.

지원 입력:
  - thiagobodruk/bible ko_ko.json (챕터가 문자열 배열의 배열)
  - 이 repo 형식 (books dict) — 그대로 복사

사용:
  python scripts/build_bible_json.py -i ko_ko.json -o data/bible-krv.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# app 패키지 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.bible import (  # noqa: E402
    BOOK_CANON_ORDER,
    BOOK_DISPLAY,
    TRANSLATION_KRV,
    _normalize_book_key,
    normalize_verse_text,
)


def convert_thiagobodruk(raw: list[Any]) -> dict[str, Any]:
    books: dict[str, Any] = {}
    for i, book in enumerate(raw):
        if not isinstance(book, dict):
            continue
        key = _normalize_book_key(str(book.get("name") or book.get("abbrev") or ""))
        if not key and i < len(BOOK_CANON_ORDER):
            key = BOOK_CANON_ORDER[i]
        if not key:
            continue

        chapters: dict[str, dict[str, str]] = {}
        for ch_idx, verses in enumerate(book.get("chapters", []), start=1):
            if not isinstance(verses, list):
                continue
            ch_map: dict[str, str] = {}
            for vs_idx, text in enumerate(verses, start=1):
                if text:
                    ch_map[str(vs_idx)] = normalize_verse_text(str(text))
            if ch_map:
                chapters[str(ch_idx)] = ch_map

        books[key] = {"name": BOOK_DISPLAY.get(key, key), "chapters": chapters}
    return {"translation": TRANSLATION_KRV, "books": books}


def normalize_books_dict(data: dict[str, Any]) -> dict[str, Any]:
    """기존 books dict — 구절 정규화·번역 메타 고정."""
    books = data.get("books")
    if not isinstance(books, dict):
        return data
    out_books: dict[str, Any] = {}
    for book_key, book_val in books.items():
        if not isinstance(book_val, dict):
            continue
        chapters = book_val.get("chapters", {})
        if not isinstance(chapters, dict):
            continue
        out_chapters: dict[str, dict[str, str]] = {}
        for ch_str, verses in chapters.items():
            if not isinstance(verses, dict):
                continue
            out_chapters[str(ch_str)] = {
                str(vs_str): normalize_verse_text(str(text))
                for vs_str, text in verses.items()
                if text
            }
        out_books[book_key] = {
            "name": book_val.get("name", book_key),
            "chapters": out_chapters,
        }
    return {"translation": TRANSLATION_KRV, "books": out_books}


def main() -> int:
    parser = argparse.ArgumentParser(description="성경 JSON 변환")
    parser.add_argument("-i", "--input", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, default=Path("data/bible-krv.json"))
    args = parser.parse_args()

    with args.input.open(encoding="utf-8-sig") as f:
        raw = json.load(f)

    if isinstance(raw, list):
        out = convert_thiagobodruk(raw)
    elif isinstance(raw, dict) and "books" in raw:
        out = normalize_books_dict(raw)
    else:
        print("지원하지 않는 입력 형식입니다.", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    verse_count = sum(
        len(vs)
        for book in out["books"].values()
        for vs in book.get("chapters", {}).values()
    )
    print(f"Wrote {args.output} ({len(out['books'])} books, {verse_count} verses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
