from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.presentations import (
    _current_preview_summary,
    _parse_groups,
    _parse_library_ids,
    _presentation_summary,
)


def test_parse_library_ids_uuid_objects():
    raw = [{"id": {"uuid": "lib-a", "name": "Default"}}]
    assert _parse_library_ids(raw) == ["lib-a"]


def test_presentation_summary_rest_groups():
    body = {
        "name": "주일 1부",
        "groups": [
            {"name": "찬양", "slides": [{}, {}, {}]},
            {"name": "말씀", "slides": [{}] * 24},
        ],
    }
    out = _presentation_summary("pres-1", "fallback", body)
    assert out["id"] == "pres-1"
    assert out["label"] == "주일 1부"
    assert out["group_count"] == 2
    assert out["slide_count"] == 27
    assert out["groups"][0] == {"label": "찬양", "slide_count": 3}


def test_parse_groups_legacy_pp():
    root = {
        "presentationSlideGroups": [
            {"groupName": "봉헌", "groupSlides": [{}, {}]},
        ],
    }
    assert _parse_groups(root) == [{"label": "봉헌", "slide_count": 2}]


def test_current_preview_summary():
    body = {
        "presentation": {
            "id": {"uuid": "pres-current-1"},
            "name": "주일예배",
            "currentSlideIndex": 4,
            "currentSlideText": "말씀 봉독",
        }
    }
    out = _current_preview_summary("hwiya-pc", body)
    assert out["venue_id"] == "hwiya-pc"
    assert out["presentation_id"] == "pres-current-1"
    assert out["label"] == "주일예배"
    assert out["current_slide_index"] == 4
    assert out["preview_text"] == "말씀 봉독"
    assert "updated_at" in out


@patch("app.main.list_venue_presentations", new_callable=AsyncMock)
def test_presentations_endpoint(mock_list):
    mock_list.return_value = {
        "venue_id": "hwiya-pc",
        "presentations": [
            {
                "id": "69796aa8-6b79-4688-b266-467e79bb3bde",
                "label": "test",
                "group_count": 1,
                "slide_count": 5,
                "groups": [{"label": "Group", "slide_count": 5}],
            }
        ],
    }
    with TestClient(app) as client:
        r = client.get("/venues/hwiya-pc/presentations")
    assert r.status_code == 200
    data = r.json()
    assert data["venue_id"] == "hwiya-pc"
    assert len(data["presentations"]) == 1
    assert data["presentations"][0]["slide_count"] == 5


def test_presentations_unknown_venue():
    with TestClient(app) as client:
        r = client.get("/venues/unknown/presentations")
    assert r.status_code == 404


@patch("app.main.get_current_presentation_preview", new_callable=AsyncMock)
def test_current_presentation_endpoint(mock_current):
    mock_current.return_value = {
        "venue_id": "hwiya-pc",
        "presentation_id": "pres-current-1",
        "label": "주일예배",
        "current_slide_index": 2,
        "preview_text": "광고",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    with TestClient(app) as client:
        r = client.get("/venues/hwiya-pc/presentation/current")
    assert r.status_code == 200
    data = r.json()
    assert data["presentation_id"] == "pres-current-1"
    assert data["current_slide_index"] == 2
