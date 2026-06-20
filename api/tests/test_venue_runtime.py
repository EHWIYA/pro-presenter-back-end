"""VenueRuntime · WorshipSession · heartbeat · worship sessions API 테스트."""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

VENUE_ID = "hwiya-pc"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_runtime_empty_db(client: TestClient):
    r = client.get(f"/api/v1/venues/{VENUE_ID}/runtime")
    assert r.status_code == 200
    data = r.json()
    assert data["venueId"] == VENUE_ID
    assert data["stale"] is True
    assert data["pp"]["reachable"] is False


@patch("app.venues_v1_api.probe_venue", new_callable=AsyncMock)
@patch("app.venues_v1_api.get_current_presentation_preview", new_callable=AsyncMock)
def test_runtime_probe(mock_preview, mock_probe, client: TestClient):
    mock_probe.return_value = {
        "connected": True,
        "agent_reachable": True,
        "checked_at": "2026-06-20T14:00:00+00:00",
    }
    mock_preview.return_value = {
        "presentation_id": "pres-uuid",
        "current_slide_index": 3,
        "preview_text": "hello",
    }
    r = client.get(f"/api/v1/venues/{VENUE_ID}/runtime/probe")
    assert r.status_code == 200
    data = r.json()
    assert data["stale"] is False
    assert data["pp"]["reachable"] is True
    assert data["pp"]["currentSlideIndex"] == 3


def test_heartbeat_requires_db(client: TestClient):
    r = client.post(
        f"/internal/agent/{VENUE_ID}/heartbeat",
        json={"agentVersion": "0.4.0", "ppReachable": True},
    )
    assert r.status_code in (200, 401, 503)


def test_heartbeat_with_key(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_HEARTBEAT_KEY", "test-agent-key")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        r = client.post(
            f"/internal/agent/{VENUE_ID}/heartbeat",
            headers={"X-Agent-Key": "test-agent-key"},
            json={
                "agentVersion": "0.4.0",
                "ppReachable": True,
                "dataGitRevision": "abc123",
                "currentSlideIndex": 2,
            },
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True

        runtime = client.get(f"/api/v1/venues/{VENUE_ID}/runtime").json()
        assert runtime["agent"]["version"] == "0.4.0"
        assert runtime["data"]["gitRevision"] == "abc123"
        assert runtime["pp"]["currentSlideIndex"] == 2
    finally:
        monkeypatch.delenv("AGENT_HEARTBEAT_KEY", raising=False)
        get_settings.cache_clear()


@patch("app.worship_sessions_api.worship_build", new_callable=AsyncMock)
def test_worship_session_create(mock_build, client: TestClient):
    mock_build.return_value = {
        "ok": True,
        "reference": "마 3:1",
        "slide_map": [{"index": 33, "label": "마 3:1"}],
        "slide_count": 1,
    }
    r = client.post(
        f"/api/v1/venues/{VENUE_ID}/worship/sessions",
        json={"text": "마 3:1"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["sessionId"]
    assert data["slide_map"][0]["index"] == 33


@patch("app.worship_sessions_api.worship_trigger", new_callable=AsyncMock)
@patch("app.worship_sessions_api.worship_build", new_callable=AsyncMock)
def test_worship_session_trigger(mock_build, mock_trigger, client: TestClient):
    mock_build.return_value = {
        "ok": True,
        "reference": "마 3:1",
        "slide_map": [{"index": 33, "label": "마 3:1"}],
    }
    mock_trigger.return_value = {"ok": True, "message": "triggered"}
    create = client.post(
        f"/api/v1/venues/{VENUE_ID}/worship/sessions",
        json={"reference": "마 3:1"},
    )
    session_id = create.json()["sessionId"]
    r = client.post(
        f"/api/v1/venues/{VENUE_ID}/worship/sessions/{session_id}/trigger",
        json={"index": 33},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_trigger.assert_awaited_once()


def test_runtime_unknown_venue(client: TestClient):
    r = client.get("/api/v1/venues/unknown/runtime")
    assert r.status_code == 404
