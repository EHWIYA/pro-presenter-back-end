"""개역개정 JSON 로드 및 한국어 성경 참조 파싱."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BOOK_ALIASES: dict[str, list[str]] = {
    "genesis": ["창세기", "창"],
    "exodus": ["출애굽기", "출"],
    "leviticus": ["레위기", "레"],
    "numbers": ["민수기", "민"],
    "deuteronomy": ["신명기", "신"],
    "joshua": ["여호수아", "수"],
    "judges": ["사사기", "삿"],
    "ruth": ["룻기", "룻"],
    "1samuel": ["사무엘상", "삼상"],
    "2samuel": ["사무엘하", "삼하"],
    "1kings": ["열왕기상", "왕상"],
    "2kings": ["열왕기하", "왕하"],
    "1chronicles": ["역대상", "대상"],
    "2chronicles": ["역대하", "대하"],
    "ezra": ["에스라", "스"],
    "nehemiah": ["느헤미야", "느"],
    "esther": ["에스더", "에"],
    "job": ["욥기", "욥"],
    "psalms": ["시편", "시"],
    "proverbs": ["잠언", "잠"],
    "ecclesiastes": ["전도서", "전"],
    "songofsongs": ["아가", "아"],
    "isaiah": ["이사야", "사"],
    "jeremiah": ["예레미야", "렘"],
    "lamentations": ["예레미야애가", "애가", "애"],
    "ezekiel": ["에스겔", "겔"],
    "daniel": ["다니엘", "단"],
    "hosea": ["호세아", "호"],
    "joel": ["요엘", "욜"],
    "amos": ["아모스", "암"],
    "obadiah": ["오바댜", "옵"],
    "jonah": ["요나", "욘"],
    "micah": ["미가", "미"],
    "nahum": ["나훔", "나"],
    "habakkuk": ["하박국", "합"],
    "zephaniah": ["스바냐", "습"],
    "haggai": ["학개", "학"],
    "zechariah": ["스가랴", "슥"],
    "malachi": ["말라기", "말"],
    "matthew": ["마태복음", "마"],
    "mark": ["마가복음", "막"],
    "luke": ["누가복음", "눅"],
    "john": ["요한복음", "요"],
    "acts": ["사도행전", "행"],
    "romans": ["로마서", "롬"],
    "1corinthians": ["고린도전서", "고전"],
    "2corinthians": ["고린도후서", "고후"],
    "galatians": ["갈라디아서", "갈"],
    "ephesians": ["에베소서", "엡"],
    "philippians": ["빌립보서", "빌"],
    "colossians": ["골로새서", "골"],
    "1thessalonians": ["데살로니가전서", "살전"],
    "2thessalonians": ["데살로니가후서", "살후"],
    "1timothy": ["디모데전서", "딤전"],
    "2timothy": ["디모데후서", "딤후"],
    "titus": ["디도서", "딛"],
    "philemon": ["빌레몬서", "몬"],
    "hebrews": ["히브리서", "히"],
    "james": ["야고보서", "약"],
    "1peter": ["베드로전서", "벧전"],
    "2peter": ["베드로후서", "벧후"],
    "1john": ["요한일서", "요일"],
    "2john": ["요한이서", "요이"],
    "3john": ["요한삼서", "요삼"],
    "jude": ["유다서", "유"],
    "revelation": ["요한계시록", "계시록", "계"],
}

BOOK_CANON_ORDER: list[str] = list(BOOK_ALIASES.keys())

BOOK_DISPLAY: dict[str, str] = {key: aliases[0] for key, aliases in BOOK_ALIASES.items()}

_ALIAS_TO_KEY: dict[str, str] = {}
for key, aliases in BOOK_ALIASES.items():
    for alias in aliases:
        _ALIAS_TO_KEY[alias] = key

_SORTED_ALIASES = sorted(_ALIAS_TO_KEY.keys(), key=len, reverse=True)

_REF_RE = re.compile(
    r"^\s*(?P<book>.+?)\s+"
    r"(?P<chapter>\d+)\s*:\s*"
    r"(?P<verse>\d+)"
    r"(?:\s*-\s*(?P<verse_end>\d+))?\s*$"
)


class BibleError(Exception):
    """성경 조회/파싱 오류."""


@dataclass(frozen=True)
class ParsedReference:
    book_key: str
    chapter: int
    verse: int
    verse_end: int | None


@dataclass(frozen=True)
class VerseResult:
    reference: str
    book_key: str
    book_name: str
    chapter: int
    verse: int
    verse_end: int | None
    title: str
    body: str


class BibleStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: Any | None = None
        self._index: dict[tuple[str, int, int], str] | None = None

    @property
    def verse_count(self) -> int:
        return len(self._build_index())

    def _load_raw(self) -> Any:
        if self._data is None:
            if not self.path.is_file():
                raise BibleError(
                    f"성경 데이터 파일이 없습니다: {self.path}. "
                    "api/scripts/build_bible_json.py 로 생성하거나 "
                    "data/bible-krv.sample.json 을 bible-krv.json 으로 복사하세요."
                )
            with self.path.open(encoding="utf-8") as f:
                self._data = json.load(f)
        return self._data

    def _build_index(self) -> dict[tuple[str, int, int], str]:
        if self._index is not None:
            return self._index

        raw = self._load_raw()
        index: dict[tuple[str, int, int], str] = {}

        if isinstance(raw, dict) and "books" in raw and isinstance(raw["books"], dict):
            for book_key, book_val in raw["books"].items():
                canonical = _normalize_book_key(book_key)
                if not canonical:
                    continue
                chapters = book_val.get("chapters", book_val) if isinstance(book_val, dict) else {}
                if isinstance(chapters, dict):
                    for ch_str, verses in chapters.items():
                        if not isinstance(verses, dict):
                            continue
                        ch = int(ch_str)
                        for vs_str, text in verses.items():
                            if text:
                                index[(canonical, ch, int(vs_str))] = str(text).strip()
        elif isinstance(raw, list):
            for i, book in enumerate(raw):
                if not isinstance(book, dict):
                    continue
                canonical = _normalize_book_key(
                    str(book.get("id") or book.get("abbrev") or book.get("name") or "")
                )
                if not canonical and i < len(BOOK_CANON_ORDER):
                    canonical = BOOK_CANON_ORDER[i]
                if not canonical:
                    continue

                chapters = book.get("chapters", [])
                if chapters and isinstance(chapters[0], list):
                    for ch_idx, verses in enumerate(chapters, start=1):
                        if not isinstance(verses, list):
                            continue
                        for vs_idx, text in enumerate(verses, start=1):
                            if text:
                                index[(canonical, ch_idx, vs_idx)] = str(text).strip()
                else:
                    for chapter in chapters:
                        if not isinstance(chapter, dict):
                            continue
                        ch = int(chapter.get("chapter") or chapter.get("number"))
                        for verse in chapter.get("verses", []):
                            vs = int(verse.get("verse") or verse.get("number"))
                            text = verse.get("text") or verse.get("content", "")
                            if text:
                                index[(canonical, ch, vs)] = str(text).strip()
        else:
            raise BibleError("지원하지 않는 성경 JSON 형식입니다.")

        if not index:
            raise BibleError("성경 JSON에서 구절을 읽지 못했습니다.")

        self._index = index
        return index

    def lookup(self, reference: str) -> VerseResult:
        parsed = parse_reference(reference)
        index = self._build_index()
        body, ref_label = _collect_verse_text(index, parsed)
        book_name = BOOK_DISPLAY.get(parsed.book_key, parsed.book_key)
        title = ref_label
        return VerseResult(
            reference=ref_label,
            book_key=parsed.book_key,
            book_name=book_name,
            chapter=parsed.chapter,
            verse=parsed.verse,
            verse_end=parsed.verse_end,
            title=title,
            body=body,
        )


def parse_reference(reference: str) -> ParsedReference:
    ref = reference.strip()
    if not ref:
        raise BibleError("성경 참조가 비어 있습니다.")

    m = _REF_RE.match(ref)
    if not m:
        raise BibleError(
            f"'{reference}' 형식을 이해하지 못했습니다. "
            "예: 요 3:16, 요한복음 3:16, 창 1:1, 롬 8:28-30"
        )

    book_part = m.group("book").strip()
    chapter = int(m.group("chapter"))
    verse = int(m.group("verse"))
    verse_end = int(m.group("verse_end")) if m.group("verse_end") else None

    if verse_end is not None and verse_end < verse:
        raise BibleError(f"절 범위가 올바르지 않습니다: {verse}-{verse_end}")

    book_key = resolve_book_key(book_part)
    if not book_key:
        raise BibleError(f"알 수 없는 성경 책 이름입니다: '{book_part}'")

    return ParsedReference(
        book_key=book_key,
        chapter=chapter,
        verse=verse,
        verse_end=verse_end,
    )


def _collect_verse_text(
    index: dict[tuple[str, int, int], str],
    parsed: ParsedReference,
) -> tuple[str, str]:
    book_name = BOOK_DISPLAY.get(parsed.book_key, parsed.book_key)
    end = parsed.verse_end or parsed.verse
    parts: list[str] = []

    for v in range(parsed.verse, end + 1):
        text = index.get((parsed.book_key, parsed.chapter, v))
        if text is None:
            raise BibleError(
                f"{book_name} {parsed.chapter}:{v} 절을 데이터에서 찾을 수 없습니다. "
                "전체 성경 JSON이 배치되었는지 확인하세요."
            )
        parts.append(text)

    if parsed.verse_end:
        ref_label = f"{book_name} {parsed.chapter}:{parsed.verse}-{parsed.verse_end}"
    else:
        ref_label = f"{book_name} {parsed.chapter}:{parsed.verse}"

    return " ".join(parts), ref_label


def resolve_book_key(book_part: str) -> str | None:
    compact = book_part.replace(" ", "")
    for alias in _SORTED_ALIASES:
        if compact == alias.replace(" ", "") or book_part == alias:
            return _ALIAS_TO_KEY[alias]
    lower = book_part.lower()
    if lower in BOOK_ALIASES:
        return lower
    return _ALIAS_TO_KEY.get(book_part)


def _normalize_book_key(raw: str) -> str | None:
    raw = raw.strip()
    if raw in BOOK_ALIASES:
        return raw
    resolved = resolve_book_key(raw)
    if resolved:
        return resolved
    lower = raw.lower()
    if lower in BOOK_ALIASES:
        return lower
    return None


def list_books() -> list[dict[str, str]]:
    return [
        {
            "id": key,
            "name": BOOK_DISPLAY[key],
            "short": BOOK_ALIASES[key][-1],
        }
        for key in BOOK_CANON_ORDER
    ]
