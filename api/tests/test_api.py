import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("VENUES_JSON_PATH", str(Path(__file__).resolve().parents[2] / "live" / "venues.json"))
os.environ.setdefault("BIBLE_JSON_PATH", str(Path(__file__).resolve().parents[1] / "data" / "bible-krv.sample.json"))

from app.main import app  # noqa: E402


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
        assert any(v["id"] == "main" for v in r.json()["venues"])
