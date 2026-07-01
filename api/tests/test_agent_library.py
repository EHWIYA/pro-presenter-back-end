from datetime import date

import pytest

from app.agent_library import (
    AgentLibraryError,
    default_scripture_presentation_filename,
    normalize_presentation_filename,
    resolve_scripture_presentation_filename,
    resolve_song_library_category,
    song_category_to_library_category,
)


def test_default_scripture_presentation_filename():
    assert default_scripture_presentation_filename(service_date=date(2026, 7, 1)) == "260701-말씀.pro"


def test_normalize_presentation_filename_adds_pro():
    assert normalize_presentation_filename("260701-말씀") == "260701-말씀.pro"


def test_resolve_scripture_presentation_filename_default():
    assert resolve_scripture_presentation_filename(None).endswith("-말씀.pro")


def test_resolve_scripture_presentation_filename_invalid():
    with pytest.raises(AgentLibraryError):
        normalize_presentation_filename("bad<name.pro")


def test_song_category_to_library_category():
    assert song_category_to_library_category("praise") == "찬양"
    assert song_category_to_library_category("hymn") == "성가곡"
    assert song_category_to_library_category("special") == "찬양"


def test_resolve_song_library_category_hymnal_title():
    assert (
        resolve_song_library_category(
            song_title="413.내 평생에 가는 길",
            song_category="hymn",
        )
        == "찬송가"
    )


def test_resolve_song_library_category_hymn_name():
    assert (
        resolve_song_library_category(
            song_title="주의 축복 내려주소서",
            song_category="hymn",
        )
        == "성가곡"
    )


def test_resolve_song_library_category_override():
    assert (
        resolve_song_library_category(
            song_title="아무 곡",
            song_category="praise",
            override="찬송가",
        )
        == "찬송가"
    )


def test_resolve_song_library_category_invalid_override():
    with pytest.raises(AgentLibraryError):
        resolve_song_library_category(song_title="x", override="예배")
