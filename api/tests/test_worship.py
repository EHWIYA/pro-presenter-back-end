from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.worship import build_agent_body, text_to_reference


def test_text_to_reference_first_line():
    assert text_to_reference("마 3:1-10\n마 3:2") == "마 3:1-10"


def test_text_to_reference_single_line():
    assert text_to_reference("  요 3:16  ") == "요 3:16"


def test_build_agent_body_defaults():
    from app.config import Settings

    settings = Settings()
    body = build_agent_body("마 3:1", settings)
    assert body["reference"] == "마 3:1"
    assert body["group_theme_key"] == "reader-context"
    assert body["build_mode"] == "append"
    assert body["auto_trigger"] is False
    assert body["library_category"] == "말씀"


def test_build_agent_body_overrides():
    from app.config import Settings

    settings = Settings()
    body = build_agent_body(
        "마 3:1",
        settings,
        auto_trigger=True,
        build_mode="replace",
        group_theme_key="sermon",
    )
    assert body["auto_trigger"] is True
    assert body["build_mode"] == "replace"
    assert body["group_theme_key"] == "sermon"


@patch("app.worship._agent_post", new_callable=AsyncMock)
def test_venue_v1_build_with_reference(mock_post):
    mock_post.return_value = {
        "ok": True,
        "slide_map": [{"index": 1, "label": "마 3:1"}],
    }
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/venues/hwiya-pc/build",
            json={"reference": "마 3:1", "auto_trigger": False},
        )
    assert r.status_code == 200
    agent_body = mock_post.await_args.kwargs["json_body"]
    assert agent_body["reference"] == "마 3:1"
    assert agent_body["auto_trigger"] is False


@patch("app.worship._agent_post", new_callable=AsyncMock)
def test_venue_v1_trigger_query_index(mock_post):
    mock_post.return_value = {"ok": True}
    with TestClient(app) as client:
        r = client.post("/api/v1/venues/hwiya-pc/trigger?index=33")
    assert r.status_code == 200
    assert mock_post.await_args.args[2] == "/trigger?index=33"


@patch("app.worship._agent_post", new_callable=AsyncMock)
def test_worship_build_endpoint(mock_post):
    mock_post.return_value = {
        "ok": True,
        "reference": "마 3:1",
        "slide_count": 1,
        "slide_map": [{"index": 33, "label": "마 3:1", "preview": "..."}],
        "message": "built",
    }
    with TestClient(app) as client:
        r = client.post(
            "/venues/hwiya-pc/worship/build",
            json={"text": "마 3:1"},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["slide_map"][0]["index"] == 33
    mock_post.assert_awaited_once()


@patch("app.worship._agent_post", new_callable=AsyncMock)
def test_worship_trigger_endpoint(mock_post):
    mock_post.return_value = {"ok": True, "message": "triggered"}
    with TestClient(app) as client:
        r = client.post(
            "/venues/hwiya-pc/worship/trigger",
            json={"index": 33},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_post.assert_awaited_once()
    assert mock_post.await_args.args[2] == "/trigger?index=33"


def test_worship_build_unknown_venue():
    with TestClient(app) as client:
        r = client.post(
            "/venues/unknown/worship/build",
            json={"text": "마 3:1"},
        )
    assert r.status_code == 404


def test_worship_build_empty_text():
    with TestClient(app) as client:
        r = client.post(
            "/venues/hwiya-pc/worship/build",
            json={"text": "   \n  "},
        )
    assert r.status_code == 422
