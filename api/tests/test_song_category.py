"""카테고리 마스터 API · slug 규칙."""

from __future__ import annotations

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.song_category import (
    make_custom_category_id,
    slugify_category_label,
    validate_category_label,
)
from app.song_category import SongCategoryError


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_slugify_matches_frontend_examples():
    assert slugify_category_label("주일 1부") == "주일-1부"
    assert slugify_category_label("  특별 찬양  ") == "특별-찬양"
    assert make_custom_category_id("주일 1부") == "custom:주일-1부"


def test_validate_category_label_rejects_builtin_names():
    with pytest.raises(SongCategoryError):
        validate_category_label("찬양")
    with pytest.raises(SongCategoryError):
        validate_category_label("성가곡")


def test_song_categories_crud(client: TestClient):
    listed = client.get("/api/v1/song-categories")
    assert listed.status_code == 200
    assert listed.json()["builtin"] == ["praise", "hymn", "special"]
    assert listed.json()["custom"] == []

    created = client.post(
        "/api/v1/song-categories",
        json={"label": "주일 1부"},
    )
    assert created.status_code == 201
    data = created.json()
    assert data["id"] == "custom:주일-1부"
    assert data["label"] == "주일 1부"
    assert "createdAt" in data

    dup = client.post(
        "/api/v1/song-categories",
        json={"label": "주일 1부"},
    )
    assert dup.status_code == 409

    cat_id = quote("custom:주일-1부", safe="")
    patched = client.patch(
        f"/api/v1/song-categories/{cat_id}",
        json={"label": "주일 예배 1부"},
    )
    assert patched.status_code == 200
    assert patched.json()["label"] == "주일 예배 1부"
    assert patched.json()["id"] == "custom:주일-1부"

    song = client.post(
        "/api/v1/songs",
        json={
            "title": "카테고리연동곡",
            "category": "custom:주일-1부",
            "sections": [{"type": "verse", "label": "1절", "lines": ["a"]}],
        },
    )
    assert song.status_code == 201

    blocked = client.delete(f"/api/v1/song-categories/{cat_id}")
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["detail"] == "category_in_use"
    assert detail["songCount"] == 1

    client.delete(f"/api/v1/songs/{song.json()['songId']}")
    deleted = client.delete(f"/api/v1/song-categories/{cat_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_song_rejects_unregistered_custom_category(client: TestClient):
    r = client.post(
        "/api/v1/songs",
        json={
            "title": "미등록카테고리",
            "category": "custom:없는-카테고리",
            "sections": [{"type": "verse", "label": "1절", "lines": ["a"]}],
        },
    )
    assert r.status_code == 422


def test_builtin_category_not_mutable(client: TestClient):
    r = client.patch(
        "/api/v1/song-categories/praise",
        json={"label": "바꿈"},
    )
    assert r.status_code == 404

    r2 = client.delete("/api/v1/song-categories/hymn")
    assert r2.status_code == 404


def test_create_category_validation(client: TestClient):
    assert client.post("/api/v1/song-categories", json={"label": ""}).status_code == 422
    assert (
        client.post("/api/v1/song-categories", json={"label": "찬양"}).status_code == 422
    )
    assert (
        client.post("/api/v1/song-categories", json={"label": "x" * 25}).status_code
        == 422
    )
