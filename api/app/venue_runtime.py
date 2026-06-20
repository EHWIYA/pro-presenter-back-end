"""VenueRuntime DB 서비스."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import VenueRuntime


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def _is_stale(updated_at: datetime | None, stale_sec: float) -> bool:
    if updated_at is None:
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    age = (datetime.now(UTC) - updated_at).total_seconds()
    return age > stale_sec


def runtime_row_to_response(
    venue_id: str,
    row: VenueRuntime | None,
    *,
    settings: Settings,
    stale_override: bool | None = None,
) -> dict[str, Any]:
    stale = stale_override if stale_override is not None else _is_stale(
        row.updated_at if row else None, settings.runtime_stale_sec
    )
    if row is None:
        return {
            "venueId": venue_id,
            "updatedAt": None,
            "stale": True,
            "pp": {
                "reachable": False,
                "currentPresentationId": None,
                "currentSlideIndex": None,
                "previewText": "",
            },
            "agent": {
                "reachable": False,
                "version": None,
                "lastHeartbeatAt": None,
            },
            "data": {
                "gitRevision": None,
                "reportedAt": None,
            },
            "lastBuild": None,
        }

    last_build = None
    if row.last_build_session_id is not None:
        last_build = {
            "sessionId": str(row.last_build_session_id),
            "kind": row.last_build_kind,
            "reference": row.last_build_reference,
            "slideMap": row.last_build_slide_map or [],
            "builtAt": _iso(row.last_build_at),
        }

    return {
        "venueId": venue_id,
        "updatedAt": _iso(row.updated_at),
        "stale": stale,
        "pp": {
            "reachable": bool(row.pp_reachable),
            "currentPresentationId": row.pp_current_presentation_id,
            "currentSlideIndex": row.pp_current_slide_index,
            "previewText": row.pp_preview_text or "",
        },
        "agent": {
            "reachable": bool(row.agent_reachable),
            "version": row.agent_version,
            "lastHeartbeatAt": _iso(row.agent_last_heartbeat_at),
        },
        "data": {
            "gitRevision": row.data_git_revision,
            "reportedAt": _iso(row.data_reported_at),
        },
        "lastBuild": last_build,
    }


async def get_runtime_row(session: AsyncSession, venue_id: str) -> VenueRuntime | None:
    result = await session.execute(
        select(VenueRuntime).where(VenueRuntime.venue_id == venue_id)
    )
    return result.scalar_one_or_none()


async def upsert_runtime_from_heartbeat(
    session: AsyncSession,
    venue_id: str,
    payload: dict[str, Any],
) -> VenueRuntime:
    now = datetime.now(UTC)
    row = await get_runtime_row(session, venue_id)
    if row is None:
        row = VenueRuntime(venue_id=venue_id)
        session.add(row)

    row.updated_at = now
    row.agent_reachable = bool(
        payload.get("agent_reachable", payload.get("pp_reachable", True))
    )
    if payload.get("agent_version") is not None:
        row.agent_version = str(payload["agent_version"])
    row.agent_last_heartbeat_at = now

    if payload.get("pp_reachable") is not None:
        row.pp_reachable = bool(payload["pp_reachable"])
    if payload.get("current_slide_index") is not None:
        row.pp_current_slide_index = int(payload["current_slide_index"])

    if payload.get("data_git_revision"):
        row.data_git_revision = str(payload["data_git_revision"])
        row.data_reported_at = now

    last_build = payload.get("last_build")
    if isinstance(last_build, dict):
        slide_map = last_build.get("slide_map") or last_build.get("slideMap")
        if slide_map is not None:
            row.last_build_slide_map = slide_map
        reference = last_build.get("reference")
        if reference:
            row.last_build_reference = str(reference)
            row.last_build_at = now
        kind = last_build.get("kind")
        if kind:
            row.last_build_kind = str(kind)
        session_id = last_build.get("session_id") or last_build.get("sessionId")
        if session_id:
            try:
                row.last_build_session_id = uuid.UUID(str(session_id))
            except ValueError:
                pass

    await session.commit()
    await session.refresh(row)
    return row


async def update_runtime_from_build(
    session: AsyncSession,
    venue_id: str,
    *,
    session_id: uuid.UUID,
    kind: str,
    reference: str,
    slide_map: list[dict[str, Any]],
) -> VenueRuntime:
    now = datetime.now(UTC)
    row = await get_runtime_row(session, venue_id)
    if row is None:
        row = VenueRuntime(venue_id=venue_id)
        session.add(row)

    row.updated_at = now
    row.last_build_session_id = session_id
    row.last_build_kind = kind
    row.last_build_reference = reference
    row.last_build_slide_map = slide_map
    row.last_build_at = now
    await session.commit()
    await session.refresh(row)
    return row


async def merge_probe_into_runtime(
    session: AsyncSession,
    venue_id: str,
    probe: dict[str, Any],
    pp_preview: dict[str, Any] | None,
) -> VenueRuntime:
    now = datetime.now(UTC)
    row = await get_runtime_row(session, venue_id)
    if row is None:
        row = VenueRuntime(venue_id=venue_id)
        session.add(row)

    row.updated_at = now
    row.pp_reachable = bool(probe.get("connected"))
    row.agent_reachable = bool(probe.get("agent_reachable"))
    if pp_preview:
        row.pp_current_presentation_id = pp_preview.get("presentation_id")
        row.pp_current_slide_index = pp_preview.get("current_slide_index")
        row.pp_preview_text = pp_preview.get("preview_text") or ""

    await session.commit()
    await session.refresh(row)
    return row
