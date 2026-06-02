from pathlib import Path

import pytest

from app.bible import (
    BibleStore,
    TRANSLATION_KRV,
    list_books,
    normalize_verse_text,
    parse_reference,
    resolve_book_key,
)
from app.split import split_two_lines

DATA = Path(__file__).resolve().parents[1] / "data" / "bible-krv.sample.json"


def test_resolve_book_aliases():
    assert resolve_book_key("요") == "john"
    assert resolve_book_key("요한복음") == "john"
    assert resolve_book_key("창") == "genesis"


def test_parse_reference():
    assert parse_reference("요 3:16").verse == 16
    assert parse_reference("창세기 1:1").book_key == "genesis"


def test_parse_reference_range():
    parsed = parse_reference("요 3:16-16")
    assert parsed.verse_end == 16


def test_normalize_verse_text_strips_quotes():
    assert normalize_verse_text(' "말씀" ') == "말씀"
    assert normalize_verse_text("''하나'' 둘") == "하나 둘"
    assert normalize_verse_text("\u201c인용\u201d") == "인용"


def test_lookup_sample_verses():
    store = BibleStore(DATA)
    assert store.translation == TRANSLATION_KRV
    j = store.lookup("요 3:16")
    assert "사랑" in j.body
    assert '"' not in j.body and "'" not in j.body
    g = store.lookup("창 1:1")
    assert "창조" in g.body


def test_lookup_strips_quotes_in_data():
    import json
    import tempfile

    payload = {
        "translation": "개역개정",
        "books": {
            "john": {
                "name": "요한복음",
                "chapters": {"3": {"16": '"하나님이" \'세상을\' 사랑하사'}},
            }
        },
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
        path = Path(f.name)
    try:
        result = BibleStore(path).lookup("요 3:16")
        assert result.body == "하나님이 세상을 사랑하사"
    finally:
        path.unlink(missing_ok=True)


def test_split_balanced_two_lines():
    text = "하나 둘 셋 넷 다섯 여섯 일곱"
    lines = split_two_lines(text, max_lines=2)
    assert len(lines) == 2
    assert " ".join(lines) == text


def test_lookup_missing_verse():
    store = BibleStore(DATA)
    with pytest.raises(Exception):
        store.lookup("요 99:99")


def test_list_books_count():
    assert len(list_books()) == 66
