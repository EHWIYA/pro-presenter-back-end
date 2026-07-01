"""ProPresenter 라이브러리 UUID 해석 — 이름 우선, stale UUID 짧은 타임아웃."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.propresenter import ProPresenterClient, ProPresenterError
from app.venues import Venue, pp_ids_for_venue, pp_library_name_for_venue


@dataclass(frozen=True)
class LibraryResolveResult:
    library_ids: list[str]
    resolved_id: str | None = None
    resolved_name: str | None = None
    source: str | None = None


def _normalize_library_name(name: str | None) -> str:
    if not name or not isinstance(name, str):
        return ""
    return name.strip().casefold()


def _parse_libraries_catalog(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    catalog: list[dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        uid = entry.get("uuid")
        if not isinstance(uid, str) or not uid.strip():
            nested = entry.get("id")
            if isinstance(nested, dict):
                uid = nested.get("uuid")
            elif isinstance(nested, str):
                uid = nested
        if not isinstance(uid, str) or not uid.strip():
            continue
        name_raw = entry.get("name")
        if isinstance(name_raw, dict):
            name_raw = name_raw.get("name")
        catalog.append(
            {
                "uuid": uid.strip(),
                "name": _normalize_library_name(name_raw if isinstance(name_raw, str) else None),
            }
        )
    return catalog


def _find_by_name(catalog: list[dict[str, str]], target_name: str) -> dict[str, str] | None:
    norm = _normalize_library_name(target_name)
    if not norm:
        return None
    for entry in catalog:
        if entry["name"] == norm:
            return entry
    return None


async def _fetch_libraries_catalog(
    client: ProPresenterClient,
    settings: Settings,
) -> list[dict[str, str]]:
    try:
        raw = await client.get_json(
            "/v1/libraries",
            timeout=settings.pp_libraries_timeout_sec,
        )
    except ProPresenterError as exc:
        if exc.status_code == 404:
            return []
        from app.presentations import _wrap_pp_error

        raise _wrap_pp_error(exc, "libraries") from exc
    return _parse_libraries_catalog(raw)


async def _configured_library_reachable(
    client: ProPresenterClient,
    library_id: str,
    settings: Settings,
) -> bool:
    try:
        await client.get_json(
            f"/v1/library/{library_id}",
            timeout=settings.pp_library_probe_timeout_sec,
        )
        return True
    except ProPresenterError:
        return False


async def resolve_venue_library(
    client: ProPresenterClient,
    venue: Venue,
    settings: Settings,
) -> LibraryResolveResult:
    """이름(기본 말씀)으로 UUID를 찾고, 설정된 ID는 짧은 probe 후 fallback."""
    target_name = pp_library_name_for_venue(venue, settings)
    configured_id = pp_ids_for_venue(venue, settings).get("library_id")
    catalog = await _fetch_libraries_catalog(client, settings)
    by_name = _find_by_name(catalog, target_name)

    if configured_id:
        configured_id = str(configured_id).strip()
        if await _configured_library_reachable(client, configured_id, settings):
            return LibraryResolveResult(
                library_ids=[configured_id],
                resolved_id=configured_id,
                resolved_name=target_name,
                source="configured_id",
            )

    if by_name:
        return LibraryResolveResult(
            library_ids=[by_name["uuid"]],
            resolved_id=by_name["uuid"],
            resolved_name=target_name,
            source="name",
        )

    if configured_id:
        return LibraryResolveResult(
            library_ids=[],
            resolved_id=None,
            resolved_name=target_name,
            source=None,
        )

    if catalog:
        ids = [e["uuid"] for e in catalog]
        return LibraryResolveResult(
            library_ids=ids,
            resolved_id=ids[0] if len(ids) == 1 else None,
            resolved_name=None,
            source="fallback",
        )

    return LibraryResolveResult(library_ids=[])


def library_resolve_probe_fields(result: LibraryResolveResult) -> dict[str, str | None]:
    return {
        "pp_library_resolved_id": result.resolved_id,
        "pp_library_resolved_name": result.resolved_name,
        "pp_library_resolve_source": result.source,
    }
