"""곡 카탈로그 API — pro-presenter-data Libraries/*.pro."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.job_context import clear_job_contexts
from app.main import app

_SONG_ID_PRAISE = "찬양/주님의 마음"
_SONG_ID_BUILD = "찬양/빌드곡"


@pytest.fixture(autouse=True)
def _reset_job_context():
    clear_job_contexts()
    yield
    clear_job_contexts()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_catalog_list_and_filter(client: TestClient):
    r = client.get("/api/v1/songs")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 3
    ids = {item["songId"] for item in data["items"]}
    assert _SONG_ID_PRAISE in ids

    hymn = client.get("/api/v1/songs", params={"category": "hymn"}).json()
    assert all(item["category"] == "hymn" for item in hymn["items"])

    hymnal = client.get(
        "/api/v1/songs", params={"libraryCategory": "찬송가"}
    ).json()
    assert hymnal["total"] >= 1
    assert hymnal["items"][0]["libraryCategory"] == "찬송가"


def test_catalog_get_detail(client: TestClient):
    encoded = quote(_SONG_ID_PRAISE, safe="")
    r = client.get(f"/api/v1/songs/{encoded}")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "주님의 마음"
    assert body["category"] == "praise"
    assert body["libraryCategory"] == "찬양"
    assert body["sections"] == []
    assert body["source"] == "data-repo"


def test_song_write_endpoints_gone(client: TestClient):
    encoded = quote(_SONG_ID_PRAISE, safe="")
    assert client.post("/api/v1/songs", json={"title": "x"}).status_code == 410
    assert client.patch(f"/api/v1/songs/{encoded}", json={"title": "y"}).status_code == 410
    assert client.delete(f"/api/v1/songs/{encoded}").status_code == 410
    assert client.put(f"/api/v1/songs/{encoded}/sections", json={"sections": []}).status_code == 410


@patch("app.songs_api.song_analyze", new_callable=AsyncMock)
def test_analyze_library_hit(mock_analyze, client: TestClient):
    r = client.post(
        "/api/v1/song/analyze",
        json={"songTitle": "주님의 마음", "lyricsText": "dummy"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "library"
    assert data["songId"] == _SONG_ID_PRAISE
    assert data["category"] == "praise"
    mock_analyze.assert_not_awaited()


@patch("app.songs_api.song_analyze", new_callable=AsyncMock)
def test_analyze_image_only_skips_library_hit(mock_analyze, client: TestClient):
    mock_analyze.return_value = {
        "jobId": "job-new-img",
        "status": "queued",
        "pollUrl": "/api/v1/song/jobs/job-new-img",
    }
    r = client.post(
        "/api/v1/song/analyze",
        json={
            "imageBase64": "aGVsbG8=",
            "imageMimeType": "image/jpeg",
        },
    )
    assert r.status_code == 202
    mock_analyze.assert_awaited_once()


@patch("app.songs_api.song_analyze", new_callable=AsyncMock)
def test_analyze_force_reanalyze(mock_analyze, client: TestClient):
    mock_analyze.return_value = {
        "jobId": "job-force",
        "status": "queued",
        "pollUrl": "/api/v1/song/jobs/job-force",
    }
    r = client.post(
        "/api/v1/song/analyze",
        json={
            "songTitle": "주님의 마음",
            "lyricsText": "dummy",
            "forceReanalyze": True,
        },
    )
    assert r.status_code == 202
    mock_analyze.assert_awaited_once()


@patch("app.songs_api.song_get_job", new_callable=AsyncMock)
def test_job_poll_no_db_save(mock_get_job, client: TestClient):
    mock_get_job.return_value = {
        "id": "job-save",
        "status": "finished",
        "parsed": {
            "song_title": "신규곡",
            "sections": [{"type": "verse", "label": "1절", "lines": ["x"]}],
        },
    }
    r = client.get("/api/v1/song/jobs/job-save")
    assert r.status_code == 200
    data = r.json()
    assert data["libraryAction"] == "skipped"
    assert data["libraryReason"] == "data-repo"
    assert "songId" not in data


@patch("app.songs_api.fetch_song_sections_from_agent", new_callable=AsyncMock)
@patch("app.worship._agent_post", new_callable=AsyncMock)
def test_build_song_by_song_id(mock_post, mock_sections, client: TestClient):
    mock_sections.return_value = [
        {"type": "verse", "label": "1절", "lines": ["a", "b"]},
    ]
    mock_post.return_value = {"slide_map": [{"index": 1}], "groups": []}

    r = client.post(
        "/api/v1/worship/build-song",
        json={"venueId": "hwiya-pc", "songId": _SONG_ID_BUILD, "buildMode": "replace"},
    )
    assert r.status_code == 200
    assert r.json()["sourceSongId"] == _SONG_ID_BUILD
    mock_sections.assert_awaited_once()
    mock_post.assert_awaited_once()
    body = mock_post.await_args.kwargs["json_body"]
    assert body["source_song_id"] == _SONG_ID_BUILD
    assert body["song_title"] == "빌드곡"
    assert body["library_category"] == "찬양"


def test_build_song_xor_validation(client: TestClient):
    r = client.post(
        "/api/v1/worship/build-song",
        json={
            "venueId": "hwiya-pc",
            "songId": _SONG_ID_BUILD,
            "songTitle": "x",
            "sections": [{"type": "verse", "label": "1", "lines": ["a"]}],
        },
    )
    assert r.status_code == 422


@patch("app.songs_api.fetch_song_sections_from_agent", new_callable=AsyncMock)
def test_venue_library_sections_proxy(mock_sections, client: TestClient):
    mock_sections.return_value = [{"type": "chorus", "label": "후렴", "lines": ["할렐루야"]}]
    encoded = quote(_SONG_ID_PRAISE, safe="")
    r = client.get(f"/api/v1/venues/hwiya-pc/library/songs/{encoded}/sections")
    assert r.status_code == 200
    assert r.json()["sections"][0]["type"] == "chorus"


def test_health_song_catalog(client: TestClient):
    body = client.get("/health").json()
    assert body["song_catalog"]["source"] == "data-repo"
    assert body["song_catalog"]["configured"] is True
    assert body["song_catalog"]["count"] >= 3
