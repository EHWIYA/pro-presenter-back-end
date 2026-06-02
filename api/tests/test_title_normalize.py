"""title-normalize.ts 동일 규칙 단위 테스트."""

from app.title_normalize import normalize_song_title


def test_normalize_korean_title():
    assert normalize_song_title("주님의 마음") == "주님의마음"


def test_normalize_whitespace():
    assert normalize_song_title(" 주님 의 마음 ") == "주님의마음"


def test_normalize_english_apostrophe():
    assert normalize_song_title("Abba's Heart") == "abbasheart"


def test_normalize_empty():
    assert normalize_song_title("") == ""
    assert normalize_song_title(None) == ""
