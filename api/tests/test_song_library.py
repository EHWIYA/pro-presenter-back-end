"""곡 라이브러리 CRUD · analyze 재사용 · build-song songId."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.job_context import clear_job_contexts
from app.main import app


@pytest.fixture(autouse=True)
def _reset_job_context():
    clear_job_contexts()
    yield
    clear_job_contexts()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _create_song(client: TestClient, title: str = "테스트곡") -> str:
    r = client.post(
        "/api/v1/songs",
        json={
            "title": title,
            "sections": [{"type": "verse", "label": "1절", "lines": ["a", "b"]}],
        },
    )
    assert r.status_code == 201
    return r.json()["songId"]


def test_song_category_filter_and_default(client: TestClient):
    r = client.post(
        "/api/v1/songs",
        json={
            "title": "성가곡테스트",
            "category": "hymn",
            "sections": [{"type": "verse", "label": "1절", "lines": ["a"]}],
        },
    )
    assert r.status_code == 201
    hymn_id = r.json()["songId"]

    r = client.post(
        "/api/v1/songs",
        json={
            "title": "기본카테고리",
            "sections": [{"type": "verse", "label": "1절", "lines": ["b"]}],
        },
    )
    assert r.status_code == 201
    default_id = r.json()["songId"]

    assert client.get(f"/api/v1/songs/{default_id}").json()["category"] == "praise"
    assert client.get(f"/api/v1/songs/{hymn_id}").json()["category"] == "hymn"

    listed = client.get("/api/v1/songs", params={"category": "hymn"}).json()
    ids = {item["songId"] for item in listed["items"]}
    assert hymn_id in ids
    assert default_id not in ids

    bad = client.post(
        "/api/v1/songs",
        json={
            "title": "잘못된카테고리",
            "category": "invalid",
            "sections": [{"type": "verse", "label": "1", "lines": ["x"]}],
        },
    )
    assert bad.status_code == 422


def test_put_sections_partial_and_empty_keeps(client: TestClient):
    song_id = _create_song(client, "구간유지곡")
    original = client.get(f"/api/v1/songs/{song_id}").json()["sections"]

    r = client.put(
        f"/api/v1/songs/{song_id}/sections",
        json={"category": "special", "title": "특송곡"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["category"] == "special"
    assert data["title"] == "특송곡"
    assert data["sections"] == original
    assert data["sectionCount"] == len(original)

    r2 = client.put(
        f"/api/v1/songs/{song_id}/sections",
        json={"sections": []},
    )
    assert r2.status_code == 200
    assert r2.json()["sections"] == original

    r3 = client.put(
        f"/api/v1/songs/{song_id}/sections",
        json={
            "sections": [
                {"type": "chorus", "label": "후렴", "lines": ["할렐루야"]},
            ],
        },
    )
    assert r3.status_code == 200
    assert len(r3.json()["sections"]) == 1
    assert r3.json()["sections"][0]["type"] == "chorus"


def test_songs_crud(client: TestClient):
    song_id = _create_song(client)

    r = client.get(f"/api/v1/songs/{song_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "테스트곡"
    assert len(r.json()["sections"]) == 1

    r = client.get("/api/v1/songs?q=테스트")
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    r = client.patch(
        f"/api/v1/songs/{song_id}",
        json={"title": "수정곡", "tags": ["예배"]},
    )
    assert r.status_code == 200

    r = client.put(
        f"/api/v1/songs/{song_id}/sections",
        json={
            "sections": [
                {"type": "chorus", "label": "후렴", "lines": ["할렐루야"]},
            ],
        },
    )
    assert r.status_code == 200

    r = client.get(f"/api/v1/songs/{song_id}")
    assert r.json()["sections"][0]["type"] == "chorus"

    r = client.delete(f"/api/v1/songs/{song_id}")
    assert r.status_code == 200
    assert client.get(f"/api/v1/songs/{song_id}").status_code == 404


@patch("app.songs_api.song_analyze", new_callable=AsyncMock)
def test_analyze_library_hit(mock_analyze, client: TestClient):
    _create_song(client, "주님의 마음")

    r = client.post(
        "/api/v1/song/analyze",
        json={"songTitle": "주님의 마음", "lyricsText": "dummy"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "library"
    assert data["category"] == "praise"
    assert data["schemaVersion"] == "song-sections/v1"
    mock_analyze.assert_not_awaited()


@patch("app.songs_api.song_analyze", new_callable=AsyncMock)
def test_analyze_image_only_skips_library_hit(mock_analyze, client: TestClient):
    mock_analyze.return_value = {
        "jobId": "job-new-img",
        "status": "queued",
        "pollUrl": "/api/v1/song/jobs/job-new-img",
    }
    _create_song(client, "주님의 마음")

    r = client.post(
        "/api/v1/song/analyze",
        json={
            "imageBase64": "aGVsbG8=",
            "imageMimeType": "image/jpeg",
        },
    )
    assert r.status_code == 202
    mock_analyze.assert_awaited_once()
    assert "songTitle" not in mock_analyze.await_args.args[1]


@patch("app.songs_api.song_analyze", new_callable=AsyncMock)
def test_analyze_force_reanalyze(mock_analyze, client: TestClient):
    mock_analyze.return_value = {
        "jobId": "job-force",
        "status": "queued",
        "pollUrl": "/api/v1/song/jobs/job-force",
    }
    _create_song(client, "주님의 마음")

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
def test_job_poll_auto_save(mock_get_job, client: TestClient):
    from app.job_context import set_job_context, AnalyzeJobContext

    set_job_context(
        "job-save",
        AnalyzeJobContext(save_to_library=True, input_kind="lyrics"),
    )
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
    assert data["libraryAction"] == "created"
    assert "songId" in data

    song_id = data["songId"]
    detail = client.get(f"/api/v1/songs/{song_id}").json()
    assert detail["title"] == "신규곡"


@patch("app.worship._agent_post", new_callable=AsyncMock)
def test_build_song_by_song_id(mock_post, client: TestClient):
    mock_post.return_value = {"slide_map": [{"index": 1}], "groups": []}
    song_id = _create_song(client, "빌드곡")

    r = client.post(
        "/api/v1/worship/build-song",
        json={"venueId": "hwiya-pc", "songId": song_id, "buildMode": "replace"},
    )
    assert r.status_code == 200
    assert r.json()["sourceSongId"] == song_id
    mock_post.assert_awaited_once()
    body = mock_post.await_args.kwargs["json_body"]
    assert body["source_song_id"] == song_id
    assert body["song_title"] == "빌드곡"


def test_build_song_xor_validation(client: TestClient):
    song_id = _create_song(client)
    r = client.post(
        "/api/v1/worship/build-song",
        json={
            "venueId": "hwiya-pc",
            "songId": song_id,
            "songTitle": "x",
            "sections": [{"type": "verse", "label": "1", "lines": ["a"]}],
        },
    )
    assert r.status_code == 422


def test_admin_import(client: TestClient, monkeypatch):
    monkeypatch.setenv("API_KEY", "test-import-key")
    from app.config import get_settings

    get_settings.cache_clear()

    ndjson = (
        '{"title":"임포트곡","sections":[{"type":"verse","label":"1","lines":["a"]}],'
        '"sourceJobId":"job-import-1"}\n'
    )
    r = client.post(
        "/api/v1/admin/songs/import",
        content=ndjson,
        headers={"X-API-Key": "test-import-key"},
    )
    assert r.status_code == 200
    assert r.json()["created"] == 1

    r2 = client.post(
        "/api/v1/admin/songs/import",
        content=ndjson,
        headers={"X-API-Key": "test-import-key"},
    )
    assert r2.json()["updated"] == 1

    get_settings.cache_clear()
