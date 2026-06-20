"""API v1 — venue runtime."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.database import get_db_session, is_db_configured
from app.presentations import PresentationsError, get_current_presentation_preview
from app.venue_runtime import (
    get_runtime_row,
    merge_probe_into_runtime,
    runtime_row_to_response,
)
from app.venues import VenueError, probe_venue

router = APIRouter(prefix="/api/v1/venues", tags=["venues-v1"])


class VenueRuntimeResponse(BaseModel):
    venueId: str
    updatedAt: str | None = None
    stale: bool = True
    pp: dict[str, Any] = Field(default_factory=dict)
    agent: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)
    lastBuild: dict[str, Any] | None = None


def _get_venues(request: Request):
    return request.app.state.venues


@router.get("/{venue_id}/runtime", response_model=VenueRuntimeResponse)
async def get_venue_runtime(
    venue_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        _get_venues(request).get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not is_db_configured():
        return runtime_row_to_response(venue_id, None, settings=settings)

    async for session in get_db_session():
        row = await get_runtime_row(session, venue_id)
        return runtime_row_to_response(venue_id, row, settings=settings)
    raise HTTPException(status_code=503, detail="DB 세션을 열 수 없습니다.")


@router.get("/{venue_id}/runtime/probe", response_model=VenueRuntimeResponse)
async def probe_venue_runtime(
    venue_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        venue = _get_venues(request).get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    probe = await probe_venue(
        venue,
        settings.pp_http_timeout_sec,
        agent_timeout=settings.agent_probe_timeout_sec,
        default_agent_port=settings.agent_port,
        settings=settings,
    )

    pp_preview: dict[str, Any] | None = None
    if probe.get("connected"):
        try:
            pp_preview = await get_current_presentation_preview(venue, settings)
        except PresentationsError:
            pp_preview = None

    if is_db_configured():
        async for session in get_db_session():
            row = await merge_probe_into_runtime(session, venue_id, probe, pp_preview)
            return runtime_row_to_response(
                venue_id, row, settings=settings, stale_override=False
            )

    stale = not (probe.get("connected") and probe.get("agent_reachable"))
    return {
        "venueId": venue_id,
        "updatedAt": probe.get("checked_at"),
        "stale": stale,
        "pp": {
            "reachable": bool(probe.get("connected")),
            "currentPresentationId": (pp_preview or {}).get("presentation_id"),
            "currentSlideIndex": (pp_preview or {}).get("current_slide_index"),
            "previewText": (pp_preview or {}).get("preview_text", ""),
        },
        "agent": {
            "reachable": bool(probe.get("agent_reachable")),
            "version": None,
            "lastHeartbeatAt": None,
        },
        "data": {"gitRevision": None, "reportedAt": None},
        "lastBuild": None,
    }
