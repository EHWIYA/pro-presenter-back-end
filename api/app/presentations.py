"""NAS → 현장 ProPresenter: 라이브러리 프레젠테이션·그룹·슬라이드 수 요약."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.library_resolve import resolve_venue_library
from app.propresenter import ProPresenterClient, ProPresenterError
from app.venues import Venue


class PresentationsError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.hint = hint


async def get_current_presentation_preview(
    venue: Venue,
    settings: Settings,
) -> dict[str, Any]:
    client = ProPresenterClient(venue, settings.pp_http_timeout_sec)
    try:
        body = await client.get_json("/v1/presentation/current")
    except ProPresenterError as exc:
        raise _wrap_pp_error(exc, "presentation/current") from exc
    return _current_preview_summary(venue.id, body)


async def list_venue_presentations(
    venue: Venue,
    settings: Settings,
) -> dict[str, Any]:
    client = ProPresenterClient(venue, settings.pp_http_timeout_sec)
    resolved = await resolve_venue_library(client, venue, settings)
    library_ids = resolved.library_ids
    if not library_ids:
        return {"venue_id": venue.id, "presentations": []}

    items: list[dict[str, Any]] = []
    for library_id in library_ids:
        try:
            raw = await client.get_json(f"/v1/library/{library_id}")
        except ProPresenterError as exc:
            raise _wrap_pp_error(exc, f"library={library_id}") from exc
        items.extend(_library_items(raw))

    if not items:
        return {"venue_id": venue.id, "presentations": []}

    presentations = await _build_presentations(client, items)
    return {"venue_id": venue.id, "presentations": presentations}


def _parse_library_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    ids: list[str] = []
    for entry in raw:
        uid = _extract_uuid(entry if isinstance(entry, dict) else {"id": entry})
        if uid and uid not in ids:
            ids.append(uid)
    return ids


def _library_items(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        items = raw.get("items")
        if isinstance(items, list):
            return [i for i in items if isinstance(i, dict)]
    if isinstance(raw, list):
        return [i for i in raw if isinstance(i, dict)]
    return []


async def _build_presentations(
    client: ProPresenterClient,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for item in items:
        uid = _extract_uuid(item)
        if not uid or uid in seen:
            continue
        seen.add(uid)
        label = _item_label(item)
        unique.append((uid, label))

    sem = asyncio.Semaphore(8)

    async def one(pres_id: str, fallback_label: str) -> dict[str, Any] | None:
        async with sem:
            try:
                body = await client.get_json(f"/v1/presentation/{pres_id}")
            except ProPresenterError:
                return None
        return _presentation_summary(pres_id, fallback_label, body)

    results = await asyncio.gather(*(one(pid, label) for pid, label in unique))
    return [r for r in results if r is not None]


def _presentation_summary(
    pres_id: str,
    fallback_label: str,
    body: Any,
) -> dict[str, Any]:
    root = body if isinstance(body, dict) else {}
    nested = root.get("presentation")
    if isinstance(nested, dict):
        root = {**nested, **{k: v for k, v in root.items() if k not in nested}}

    label = (
        root.get("name")
        or root.get("presentationName")
        or root.get("presentation_name")
        or fallback_label
        or pres_id
    )
    groups = _parse_groups(root)
    slide_count = sum(g["slide_count"] for g in groups)
    return {
        "id": pres_id,
        "label": str(label),
        "group_count": len(groups),
        "slide_count": slide_count,
        "groups": groups,
    }


def _parse_groups(root: dict[str, Any]) -> list[dict[str, Any]]:
    groups_raw = root.get("groups")
    if groups_raw is None:
        groups_raw = root.get("presentationSlideGroups")
    if not isinstance(groups_raw, list):
        return []

    groups: list[dict[str, Any]] = []
    for group in groups_raw:
        if not isinstance(group, dict):
            continue
        label = (
            group.get("name")
            or group.get("groupName")
            or group.get("group_name")
            or ""
        )
        slides = group.get("slides")
        if slides is None:
            slides = group.get("groupSlides")
        count = len(slides) if isinstance(slides, list) else 0
        groups.append({"label": str(label), "slide_count": count})
    return groups


def _current_preview_summary(venue_id: str, body: Any) -> dict[str, Any]:
    root = body if isinstance(body, dict) else {}
    nested = root.get("presentation")
    if isinstance(nested, dict):
        root = {**nested, **{k: v for k, v in root.items() if k not in nested}}

    presentation_id = _extract_uuid(root)
    label = (
        root.get("name")
        or root.get("presentationName")
        or root.get("presentation_name")
        or ""
    )
    current_slide_index = _coerce_index(
        root.get("currentSlideIndex")
        or root.get("slideIndex")
        or root.get("activeSlideIndex")
        or root.get("active_index")
    )
    preview_text = _extract_preview_text(root)

    return {
        "venue_id": venue_id,
        "presentation_id": presentation_id,
        "label": str(label),
        "current_slide_index": current_slide_index,
        "preview_text": preview_text,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _coerce_index(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _extract_preview_text(root: dict[str, Any]) -> str:
    candidates: list[str] = []
    for key in ("currentSlideText", "previewText", "text", "label"):
        value = root.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())

    slides = root.get("slides")
    if isinstance(slides, list):
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            for key in ("text", "label", "title"):
                value = slide.get(key)
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())
                    break

    if candidates:
        return candidates[0]
    return ""


def _extract_uuid(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if not isinstance(value, dict):
        return None
    for key in ("uuid", "id", "presentation_id", "presentation_uuid"):
        nested = value.get(key)
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
        if isinstance(nested, dict):
            uid = nested.get("uuid") or nested.get("id")
            if isinstance(uid, str) and uid.strip():
                return uid.strip()
    return None


def _item_label(item: dict[str, Any]) -> str:
    for key in ("name", "label", "title", "presentation_name"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _wrap_pp_error(exc: ProPresenterError, context: str) -> PresentationsError:
    hint = exc.hint
    if hint:
        hint = f"{hint} ({context})"
    else:
        hint = context
    return PresentationsError(str(exc), hint=hint)
