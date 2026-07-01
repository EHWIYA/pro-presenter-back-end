"""song_catalog.validate_section — catalog 모드(lines_per_slide) 검증."""

import pytest

from app.song_catalog import SongCatalogError, validate_section


def test_validate_section_accepts_title_type():
    validate_section({"type": "title", "label": "제목", "lines": ["곡 제목"]})


def test_validate_section_catalog_mode_allows_many_lines():
    lines = [f"줄{i}" for i in range(1, 65)]
    validate_section(
        {"type": "verse", "label": "1절", "lines": lines},
        lines_per_slide=1,
    )


def test_validate_section_catalog_mode_rejects_over_64_lines():
    lines = [f"줄{i}" for i in range(1, 66)]
    with pytest.raises(SongCatalogError, match="64"):
        validate_section(
            {"type": "verse", "label": "1절", "lines": lines},
            lines_per_slide=1,
        )


def test_validate_section_legacy_mode_rejects_three_lines():
    with pytest.raises(SongCatalogError, match="1~2"):
        validate_section(
            {"type": "verse", "label": "1절", "lines": ["a", "b", "c"]},
        )
