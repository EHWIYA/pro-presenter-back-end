from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.worship import build_song_agent_body


def test_build_song_agent_body_snake_case():
    body = build_song_agent_body(
        song_title="주님의 마음",
        build_mode="append",
        library_category="찬양",
        sections=[
            {"type": "verse", "label": "1절", "lines": ["첫 줄", "둘째 줄"]},
        ],
        source_song_id="찬양/주님의 마음",
    )
    assert body == {
        "song_title": "주님의 마음",
        "library_category": "찬양",
        "group_theme_key": "lyric",
        "build_mode": "append",
        "source_song_id": "찬양/주님의 마음",
        "sections": [
            {"type": "verse", "label": "1절", "lines": ["첫 줄", "둘째 줄"]},
        ],
    }


@patch("app.songs_api.song_analyze", new_callable=AsyncMock)
def test_song_analyze_lyrics(mock_analyze):
    mock_analyze.return_value = {
        "jobId": "job-abc",
        "status": "pending",
        "pollUrl": "/api/v1/song/jobs/job-abc",
    }
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/song/analyze",
            json={"songTitle": "미등록곡", "lyricsText": "1절 가사\n2줄"},
        )

    assert r.status_code == 202
    data = r.json()
    assert data["jobId"] == "job-abc"
    assert data["pollUrl"] == "/api/v1/song/jobs/job-abc"
    mock_analyze.assert_awaited_once()
    assert mock_analyze.await_args.args[1]["lyricsText"] == "1절 가사\n2줄"


@patch("app.songs_api.song_get_job", new_callable=AsyncMock)
def test_song_job_poll(mock_get_job):
    mock_get_job.return_value = {
        "jobId": "job-abc",
        "status": "completed",
        "parsed": {
            "sections": [
                {"type": "verse", "label": "1절", "lines": ["가", "나"]},
            ],
        },
    }
    with TestClient(app) as client:
        r = client.get("/api/v1/song/jobs/job-abc")
    assert r.status_code == 200
    assert r.json()["parsed"]["sections"][0]["lines"] == ["가", "나"]


@patch("app.worship._agent_post", new_callable=AsyncMock)
def test_worship_build_song_endpoint(mock_post):
    mock_post.return_value = {
        "ok": True,
        "slide_map": [{"index": 1, "label": "1절"}],
        "groups": [{"name": "1절", "slides": 2}],
    }
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/worship/build-song",
            json={
                "venueId": "hwiya-pc",
                "songTitle": "주님의 마음",
                "buildMode": "append",
                "sections": [
                    {"type": "verse", "label": "1절", "lines": ["첫 줄"]},
                ],
            },
        )
    assert r.status_code == 200
    assert r.json()["slide_map"][0]["label"] == "1절"
    mock_post.assert_awaited_once()
    assert mock_post.await_args.args[2] == "/build-song"
    agent_body = mock_post.await_args.kwargs["json_body"]
    assert agent_body["song_title"] == "주님의 마음"
    assert agent_body["library_category"] == "찬양"
    assert agent_body["group_theme_key"] == "lyric"


@patch("app.songs_api.song_analyze", new_callable=AsyncMock)
def test_song_analyze_image_only_no_title(mock_analyze):
    mock_analyze.return_value = {
        "jobId": "job-img",
        "status": "pending",
        "pollUrl": "/api/v1/song/jobs/job-img",
    }
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/song/analyze",
            json={
                "imageBase64": "aGVsbG8=",
                "imageMimeType": "image/jpeg",
                "saveToLibrary": True,
            },
        )

    assert r.status_code == 202
    assert r.json()["jobId"] == "job-img"
    mock_analyze.assert_awaited_once()
    upstream = mock_analyze.await_args.args[1]
    assert "songTitle" not in upstream
    assert upstream["imageBase64"] == "aGVsbG8="
    assert upstream["imageMimeType"] == "image/jpeg"


def test_song_analyze_requires_image_or_lyrics():
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/song/analyze",
            json={"songTitle": "테스트"},
        )
    assert r.status_code == 422


def test_worship_build_song_unknown_venue():
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/worship/build-song",
            json={
                "venueId": "unknown",
                "songTitle": "x",
                "sections": [{"type": "verse", "label": "1", "lines": ["a"]}],
            },
        )
    assert r.status_code == 404
