from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.presentations import (
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


@patch("app.main.list_venue_presentations", new_callable=AsyncMock)
def test_presentations_endpoint(mock_list):
    mock_list.return_value = {
        "venue_id": "main",
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
        r = client.get("/venues/main/presentations")
    assert r.status_code == 200
    data = r.json()
    assert data["venue_id"] == "main"
    assert len(data["presentations"]) == 1
    assert data["presentations"][0]["slide_count"] == 5


def test_presentations_unknown_venue():
    with TestClient(app) as client:
        r = client.get("/venues/unknown/presentations")
    assert r.status_code == 404
