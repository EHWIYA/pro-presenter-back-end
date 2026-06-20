from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app


def test_health():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["bible_verses_loaded"] >= 2


def test_books():
    with TestClient(app) as client:
        r = client.get("/api/v1/books")
        assert r.status_code == 200
        assert len(r.json()["books"]) == 66


def test_verse_parse():
    with TestClient(app) as client:
        r = client.post("/api/v1/verse/parse", json={"reference": "요 3:16"})
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "요한복음 3:16"
        assert len(data["lines"]) == 2


def test_verse_send_requires_venue():
    with TestClient(app) as client:
        r = client.post("/api/v1/verse/send", json={"reference": "요 3:16"})
        assert r.status_code == 400


def test_venues_list():
    with TestClient(app) as client:
        r = client.get("/venues")
        assert r.status_code == 200
        assert any(v["id"] == "hwiya-pc" for v in r.json()["venues"])


@patch("app.main.probe_venue", new_callable=AsyncMock)
def test_venues_status(mock_probe):
    mock_probe.side_effect = [
        {
            "venue_id": "hwiya-pc",
            "name": "Main Hall",
            "connected": True,
            "status_code": "ok",
            "message": "연결됨",
            "agent_reachable": True,
            "agent_status_code": "ok",
            "agent_message": "에이전트 연결됨",
            "checked_at": "2026-01-01T00:00:00+00:00",
        },
        {
            "venue_id": "sub",
            "name": "Sub Hall",
            "connected": False,
            "status_code": "timeout",
            "message": "요청 시간 초과 - 방화벽 또는 ProPresenter API 미응답",
            "agent_reachable": False,
            "agent_status_code": "timeout",
            "agent_message": "에이전트 응답 시간 초과",
            "checked_at": "2026-01-01T00:00:00+00:00",
        },
    ]
    with TestClient(app) as client:
        r = client.get("/venues/status")
    assert r.status_code == 200
    data = r.json()
    assert len(data["venues"]) >= 1
    assert "connected" in data["venues"][0]
    assert "agent_reachable" in data["venues"][0]
    assert "agent_status_code" in data["venues"][0]
    assert "agent_message" in data["venues"][0]
    assert "elapsed_ms" in data["venues"][0]


@patch("app.main.probe_venue", new_callable=AsyncMock)
def test_venues_status_partial_success_on_probe_exception(mock_probe):
    mock_probe.side_effect = RuntimeError("unexpected probe error")
    with TestClient(app) as client:
        r = client.get("/venues/status")
    assert r.status_code == 200
    data = r.json()["venues"]
    assert len(data) >= 1
    assert any(v["status_code"] == "internal_error" for v in data)
    assert all("agent_reachable" in v for v in data)
