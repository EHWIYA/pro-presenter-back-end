import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import Settings
from app.library_resolve import (
    _find_by_name,
    _parse_libraries_catalog,
    resolve_venue_library,
)
from app.propresenter import ProPresenterError
from app.venues import Venue


def _venue(**kwargs) -> Venue:
    defaults = {
        "id": "hwiya-pc",
        "name": "본당",
        "tailscale_ip": "100.0.0.1",
        "pp_port": 1025,
        "enabled": True,
    }
    defaults.update(kwargs)
    return Venue(**defaults)


def _settings(**kwargs) -> Settings:
    return Settings(**{**kwargs, "venues_json_path": kwargs.get("venues_json_path", "/tmp/venues.json")})


def test_parse_libraries_catalog_pp_shape():
    raw = [
        {"uuid": "0d0d3126-b870-49f1-a6a6-abd2c867c744", "name": "worship-2", "index": 0},
        {"uuid": "other", "name": "Default", "index": 1},
    ]
    catalog = _parse_libraries_catalog(raw)
    assert len(catalog) == 2
    assert catalog[0]["uuid"] == "0d0d3126-b870-49f1-a6a6-abd2c867c744"
    assert catalog[0]["name"] == "worship-2"


def test_find_by_name_trim_casefold():
    catalog = _parse_libraries_catalog([{"uuid": "u1", "name": "  Worship-2  "}])
    hit = _find_by_name(catalog, "worship-2")
    assert hit is not None
    assert hit["uuid"] == "u1"


def test_stale_configured_id_falls_back_to_name():
    venue = _venue(pp_library_id="7c0f2ee0-stale-uuid", pp_library_name="worship-2")
    settings = _settings()
    client = MagicMock()
    client.get_json = AsyncMock(
        side_effect=[
            [{"uuid": "0d0d3126-new", "name": "worship-2", "index": 0}],
            ProPresenterError("timeout", hint="library=stale"),
        ]
    )

    result = asyncio.run(resolve_venue_library(client, venue, settings))

    assert result.library_ids == ["0d0d3126-new"]
    assert result.source == "name"
    assert client.get_json.await_args_list[0].args[0] == "/v1/libraries"
    assert "stale" in client.get_json.await_args_list[1].args[0]


def test_valid_configured_id_used_without_name_fetch_delay():
    venue = _venue(pp_library_id="current-uuid", pp_library_name="worship-2")
    settings = _settings()
    client = MagicMock()
    client.get_json = AsyncMock(
        side_effect=[
            [{"uuid": "current-uuid", "name": "worship-2", "index": 0}],
            {"items": []},
        ]
    )

    result = asyncio.run(resolve_venue_library(client, venue, settings))

    assert result.library_ids == ["current-uuid"]
    assert result.source == "configured_id"


@patch("app.library_resolve._configured_library_reachable", new_callable=AsyncMock)
@patch("app.library_resolve._fetch_libraries_catalog", new_callable=AsyncMock)
def test_resolve_uses_short_timeouts(mock_catalog, mock_reachable):
    mock_catalog.return_value = [{"uuid": "by-name", "name": "worship-2"}]
    mock_reachable.return_value = False
    venue = _venue(pp_library_id="stale")
    settings = _settings(pp_library_probe_timeout_sec=2.5, pp_libraries_timeout_sec=4.0)
    client = MagicMock()

    asyncio.run(resolve_venue_library(client, venue, settings))

    mock_catalog.assert_awaited_once()
    mock_reachable.assert_awaited_once_with(client, "stale", settings)
