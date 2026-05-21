from pathlib import Path

import pytest

from app.bible import BibleStore, list_books, parse_reference, resolve_book_key
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


def test_lookup_sample_verses():
    store = BibleStore(DATA)
    j = store.lookup("요 3:16")
    assert "사랑" in j.body
    g = store.lookup("창 1:1")
    assert "창조" in g.body


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
