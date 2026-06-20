"""내부 API — 에이전트 heartbeat."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import AliasChoices, BaseModel, Field

from app.config import Settings, get_settings
from app.database import get_db_session, is_db_configured
from app.venue_runtime import upsert_runtime_from_heartbeat
from app.venues import Venue, VenueError

router = APIRouter(prefix="/internal/agent", tags=["internal"])


class HeartbeatLastBuild(BaseModel):
    slide_map: list[dict[str, Any]] | None = Field(
        default=None, validation_alias=AliasChoices("slideMap", "slide_map")
    )
    reference: str | None = None
    kind: str | None = None
    session_id: str | None = Field(
        default=None, validation_alias=AliasChoices("sessionId", "session_id")
    )


class AgentHeartbeatBody(BaseModel):
    agent_version: str | None = Field(
        default=None, validation_alias=AliasChoices("agentVersion", "agent_version")
    )
    pp_reachable: bool | None = Field(
        default=None, validation_alias=AliasChoices("ppReachable", "pp_reachable")
    )
    data_git_revision: str | None = Field(
        default=None, validation_alias=AliasChoices("dataGitRevision", "data_git_revision")
    )
    last_build: HeartbeatLastBuild | None = Field(
        default=None, validation_alias=AliasChoices("lastBuild", "last_build")
    )
    current_slide_index: int | None = Field(
        default=None, validation_alias=AliasChoices("currentSlideIndex", "current_slide_index")
    )
    agent_reachable: bool | None = Field(
        default=None, validation_alias=AliasChoices("agentReachable", "agent_reachable")
    )

    model_config = {"populate_by_name": True}


def _get_venues(request: Request):
    return request.app.state.venues


def _validate_agent_key(venue: Venue, settings: Settings, provided: str | None) -> None:
    expected = venue.agent_key or settings.agent_heartbeat_key
    if not expected:
        return
    if provided != expected:
        raise HTTPException(status_code=401, detail="유효하지 않은 에이전트 키입니다.")


@router.post("/{venue_id}/heartbeat")
async def agent_heartbeat(
    venue_id: str,
    body: AgentHeartbeatBody,
    request: Request,
    settings: Settings = Depends(get_settings),
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> dict[str, Any]:
    try:
        venue = _get_venues(request).get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _validate_agent_key(venue, settings, x_agent_key)

    if not is_db_configured():
        raise HTTPException(status_code=503, detail="DATABASE_URL이 설정되지 않았습니다.")

    payload: dict[str, Any] = {
        "agent_version": body.agent_version,
        "pp_reachable": body.pp_reachable,
        "agent_reachable": body.agent_reachable if body.agent_reachable is not None else True,
        "data_git_revision": body.data_git_revision,
        "current_slide_index": body.current_slide_index,
    }
    if body.last_build is not None:
        payload["last_build"] = body.last_build.model_dump(by_alias=False, exclude_none=True)

    async for session in get_db_session():
        row = await upsert_runtime_from_heartbeat(session, venue_id, payload)
        return {"ok": True, "venueId": venue_id, "updatedAt": row.updated_at.isoformat()}
    raise HTTPException(status_code=503, detail="DB 세션을 열 수 없습니다.")
