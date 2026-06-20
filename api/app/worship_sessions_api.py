"""API v1 — worship sessions (영속 빌드·trigger)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.database import get_db_session, is_db_configured
from app.venues import VenueError
from app.worship import WorshipError, text_to_reference, worship_build, worship_trigger
from app.worship_sessions import (
    WorshipSessionError,
    create_scripture_session,
    get_session,
    record_trigger,
)

router = APIRouter(prefix="/api/v1/venues", tags=["worship-sessions"])


class WorshipSessionBuildRequest(BaseModel):
    text: str | None = Field(default=None, examples=["마 3:1-10\n마 3:2"])
    reference: str | None = Field(default=None, examples=["마 3:1-10"])


class WorshipSessionTriggerRequest(BaseModel):
    index: int = Field(..., examples=[33])


def _get_venues(request: Request):
    return request.app.state.venues


def _resolve_reference(body: WorshipSessionBuildRequest) -> str:
    if body.reference and body.reference.strip():
        return body.reference.strip()
    if body.text and body.text.strip():
        return text_to_reference(body.text)
    raise HTTPException(status_code=400, detail="text 또는 reference가 필요합니다.")


@router.post("/{venue_id}/worship/sessions")
async def create_worship_session(
    venue_id: str,
    body: WorshipSessionBuildRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        venue = _get_venues(request).get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        reference = _resolve_reference(body)
        text = body.text or reference
        agent_result = await worship_build(venue, settings, text)
    except WorshipError as exc:
        detail: dict[str, Any] = {"message": str(exc)}
        if exc.hint:
            detail["hint"] = exc.hint
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc

    if not is_db_configured():
        return {**agent_result, "sessionId": None}

    async for session in get_db_session():
        _, response = await create_scripture_session(
            session,
            venue_id,
            reference=reference,
            agent_result=agent_result,
        )
        return response
    raise HTTPException(status_code=503, detail="DB 세션을 열 수 없습니다.")


@router.post("/{venue_id}/worship/sessions/{session_id}/trigger")
async def trigger_worship_session(
    venue_id: str,
    session_id: str,
    body: WorshipSessionTriggerRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        venue = _get_venues(request).get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        sid = uuid.UUID(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="session_id 형식이 올바르지 않습니다.") from exc

    if is_db_configured():
        async for session in get_db_session():
            worship_session = await get_session(session, venue_id, sid)
            valid_indexes = {item.get("index") for item in worship_session.slide_map}
            if body.index not in valid_indexes and worship_session.slide_map:
                raise HTTPException(
                    status_code=400,
                    detail=f"slide_map에 없는 index입니다: {body.index}",
                )
            try:
                result = await worship_trigger(venue, settings, body.index)
            except WorshipError as exc:
                detail: dict[str, Any] = {"message": str(exc)}
                if exc.hint:
                    detail["hint"] = exc.hint
                raise HTTPException(status_code=exc.status_code, detail=detail) from exc
            await record_trigger(session, worship_session, body.index)
            return {**result, "sessionId": session_id, "index": body.index}
        raise HTTPException(status_code=503, detail="DB 세션을 열 수 없습니다.")

    try:
        return await worship_trigger(venue, settings, body.index)
    except WorshipError as exc:
        detail = {"message": str(exc)}
        if exc.hint:
            detail["hint"] = exc.hint
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc
