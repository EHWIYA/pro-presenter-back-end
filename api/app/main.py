"""ProPresenter 원격 방송 API — FastAPI 진입점."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from app.bible import BibleStore, list_books
from app.config import Settings, get_settings, resolve_bible_path
from app.worship import WorshipError, worship_build, worship_trigger
from app.worship_sessions import create_scripture_session
from app.database import dispose_db, ensure_schema, get_db_session, init_db, is_db_configured
from app.songs_api import router as songs_router
from app.verse_service import VerseServiceError, parse_verse, send_verse
from app.presentations import (
    PresentationsError,
    get_current_presentation_preview,
    list_venue_presentations,
)
from app.venues import Venue, VenueError, VenueRegistry, probe_venue
from app.internal_api import router as internal_router
from app.venues_v1_api import router as venues_v1_router
from app.worship_sessions_api import router as worship_sessions_router

API_VERSION = "1.2.0"
logger = logging.getLogger(__name__)


class VerseRequest(BaseModel):
    reference: str = Field(..., examples=["요 3:16"])
    venue_id: str | None = Field(default=None, examples=["hwiya-pc"])


class VenueBuildRequest(BaseModel):
    reference: str | None = Field(default=None, examples=["마 3:1-10"])
    text: str | None = Field(default=None, examples=["마 3:1-10\n마 3:2"])
    auto_trigger: bool = Field(default=False)
    build_mode: str | None = Field(default=None, examples=["append"])
    group_theme_key: str | None = Field(default=None, examples=["reader-context"])
    library_category: str | None = Field(default=None, examples=["말씀"])
    presentation_filename: str | None = Field(
        default=None,
        examples=["260701-말씀.pro"],
        description="생략 시 KST 오늘 날짜 기준 YYMMDD-말씀.pro",
    )

    @model_validator(mode="after")
    def require_reference_or_text(self) -> VenueBuildRequest:
        has_reference = bool(self.reference and self.reference.strip())
        has_text = self.text is not None and bool(self.text.strip())
        if not has_reference and not has_text:
            raise ValueError("reference 또는 text 중 하나가 필요합니다.")
        return self


# 레거시 worship 경로 — VenueBuildRequest와 동일 스키마
WorshipBuildRequest = VenueBuildRequest


class WorshipTriggerRequest(BaseModel):
    index: int = Field(..., examples=[33])


class VenueProbeResponse(BaseModel):
    connected: bool
    venue_id: str
    name: str
    url: str | None = None
    status_code: str
    http_status: int | None = None
    message: str
    agent_reachable: bool
    agent_status_code: str
    agent_message: str
    agent_health_url: str | None = None
    checked_at: str
    elapsed_ms: int | None = None
    pp_library_resolved_id: str | None = None
    pp_library_resolved_name: str | None = None
    pp_library_resolve_source: str | None = None


class VenuesStatusResponse(BaseModel):
    venues: list[VenueProbeResponse]


def _require_api_key(
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="유효하지 않은 API 키입니다.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    bible_path = resolve_bible_path(settings.bible_json_path)
    init_db(settings)
    if is_db_configured() and settings.database_url and "sqlite" in settings.database_url:
        await ensure_schema()
    app.state.settings = settings
    app.state.bible = BibleStore(bible_path)
    app.state.venues = VenueRegistry(settings.venues_json_path)
    yield
    await dispose_db()


app = FastAPI(
    title="ProPresenter Live API",
    version=API_VERSION,
    description="성경 구절·찬양 곡 라이브러리·ProPresenter 송출",
    lifespan=lifespan,
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(songs_router)
app.include_router(venues_v1_router)
app.include_router(worship_sessions_router)
app.include_router(internal_router)


@app.get("/health")
async def health() -> dict[str, Any]:
    from app.config import get_settings
    from app.song_catalog import catalog_status

    bible: BibleStore = app.state.bible
    settings = get_settings()
    return {
        "status": "ok",
        "version": API_VERSION,
        "bible_path": str(bible.path),
        "bible_translation": bible.translation,
        "bible_verses_loaded": bible.verse_count,
        "database_configured": is_db_configured(),
        "song_catalog": catalog_status(settings),
    }


@app.get("/api/v1/books")
async def books() -> dict[str, Any]:
    return {"books": list_books()}


@app.get("/venues")
async def list_venues() -> dict[str, Any]:
    return {"venues": _get_venues().list_public()}


@app.get("/venues/{venue_id}/probe", response_model=VenueProbeResponse)
async def venue_probe(
    venue_id: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        venue = _get_venues().get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await probe_venue(
        venue,
        settings.pp_http_timeout_sec,
        agent_timeout=settings.agent_probe_timeout_sec,
        default_agent_port=settings.agent_port,
        settings=settings,
    )


@app.get("/venues/status", response_model=VenuesStatusResponse)
async def venues_status(
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    venues = [v for v in _get_venues().all() if v.enabled]
    wall = settings.venues_status_wall_timeout_sec
    try:
        probes = await asyncio.wait_for(
            asyncio.gather(*(_probe_venue_safe(venue, settings) for venue in venues)),
            timeout=wall,
        )
    except TimeoutError:
        logger.warning("venues/status wall timeout exceeded (%.1fs)", wall)
        probes = [
            {
                "connected": False,
                "venue_id": venue.id,
                "name": venue.name,
                "status_code": "wall_timeout",
                "message": f"전체 상태 점검 시간 초과 ({wall:.0f}s)",
                "agent_reachable": False,
                "agent_status_code": "wall_timeout",
                "agent_message": "전체 상태 점검 시간 초과",
                "checked_at": datetime.now(UTC).isoformat(),
            }
            for venue in venues
        ]
    return {"venues": list(probes)}


@app.get("/venues/{venue_id}/presentations")
async def venue_presentations(
    venue_id: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        venue = _get_venues().get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return await list_venue_presentations(venue, settings)
    except PresentationsError as exc:
        raise _http_from_presentations(exc) from exc


@app.get("/venues/{venue_id}/presentation/current")
async def venue_current_presentation(
    venue_id: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        venue = _get_venues().get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return await get_current_presentation_preview(venue, settings)
    except PresentationsError as exc:
        raise _http_from_presentations(exc) from exc


@app.post("/api/v1/venues/{venue_id}/build")
@app.post("/venues/{venue_id}/worship/build", deprecated=True)
async def venue_worship_build(
    venue_id: str,
    body: VenueBuildRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """하위 호환 — `POST /api/v1/venues/{id}/worship/sessions` 권장."""
    try:
        venue = _get_venues().get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        result = await worship_build(
            venue,
            settings,
            reference=body.reference,
            text=body.text,
            auto_trigger=body.auto_trigger,
            build_mode=body.build_mode,
            group_theme_key=body.group_theme_key,
            library_category=body.library_category,
            presentation_filename=body.presentation_filename,
        )
        if is_db_configured():
            reference = result.get("reference")
            if not reference:
                from app.worship import resolve_build_reference

                reference = resolve_build_reference(
                    reference=body.reference, text=body.text
                )
            async for session in get_db_session():
                _, enriched = await create_scripture_session(
                    session,
                    venue_id,
                    reference=str(reference),
                    agent_result=result,
                    presentation_filename=body.presentation_filename,
                    library_category=body.library_category,
                )
                return enriched
        return result
    except WorshipError as exc:
        raise _http_from_worship(exc) from exc


@app.post("/api/v1/venues/{venue_id}/trigger")
@app.post("/venues/{venue_id}/worship/trigger")
async def venue_worship_trigger(
    venue_id: str,
    settings: Settings = Depends(get_settings),
    index: int | None = Query(default=None, description="송출할 slide_map index"),
    body: WorshipTriggerRequest | None = None,
) -> dict[str, Any]:
    resolved_index = index if index is not None else (body.index if body is not None else None)
    if resolved_index is None:
        raise HTTPException(status_code=400, detail="index가 필요합니다.")
    try:
        venue = _get_venues().get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return await worship_trigger(venue, settings, resolved_index)
    except WorshipError as exc:
        raise _http_from_worship(exc) from exc


@app.post("/api/v1/verse/parse", dependencies=[Depends(_require_api_key)])
async def verse_parse(body: VerseRequest) -> dict[str, Any]:
    try:
        return await parse_verse(_get_bible(), body.reference)
    except VerseServiceError as exc:
        raise _http_from_service(exc) from exc


@app.post("/api/v1/verse/send", dependencies=[Depends(_require_api_key)], deprecated=True)
async def verse_send(body: VerseRequest) -> dict[str, Any]:
    """레거시 — 신규 UI에서 사용 금지. worship sessions + trigger 사용."""
    if not body.venue_id:
        raise HTTPException(status_code=400, detail="venue_id가 필요합니다.")
    try:
        return await send_verse(
            _get_bible(),
            _get_venues(),
            get_settings(),
            body.reference,
            body.venue_id,
        )
    except VerseServiceError as exc:
        raise _http_from_service(exc) from exc


def _get_bible() -> BibleStore:
    return app.state.bible


def _get_venues() -> VenueRegistry:
    return app.state.venues


def _http_from_service(exc: VerseServiceError) -> HTTPException:
    detail: dict[str, Any] = {"message": str(exc)}
    if exc.hint:
        detail["hint"] = exc.hint
    return HTTPException(status_code=exc.status_code, detail=detail)


def _http_from_worship(exc: WorshipError) -> HTTPException:
    detail: dict[str, Any] = {"message": str(exc)}
    if exc.hint:
        detail["hint"] = exc.hint
    return HTTPException(status_code=exc.status_code, detail=detail)


def _http_from_presentations(exc: PresentationsError) -> HTTPException:
    detail: dict[str, Any] = {"message": str(exc)}
    if exc.hint:
        detail["hint"] = exc.hint
    return HTTPException(status_code=exc.status_code, detail=detail)


async def _probe_venue_safe(venue: Venue, settings: Settings) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = await probe_venue(
            venue,
            settings.pp_http_timeout_sec,
            agent_timeout=settings.agent_probe_timeout_sec,
            default_agent_port=settings.agent_port,
            settings=settings,
        )
    except Exception:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.exception(
            "venues/status probe failed venue_id=%s elapsed_ms=%s",
            venue.id,
            elapsed_ms,
        )
        return {
            "connected": False,
            "venue_id": venue.id,
            "name": venue.name,
            "status_code": "internal_error",
            "message": "상태 점검 중 내부 오류가 발생했습니다.",
            "agent_reachable": False,
            "agent_status_code": "unknown",
            "agent_message": "에이전트 상태를 확인하지 못했습니다.",
            "checked_at": datetime.now(UTC).isoformat(),
        }

    elapsed_ms = int((time.monotonic() - started) * 1000)
    result.setdefault("agent_reachable", False)
    result.setdefault("agent_status_code", "unknown")
    result.setdefault("agent_message", "에이전트 상태를 확인하지 못했습니다.")
    logger.info(
        "venues/status probe venue_id=%s connected=%s status_code=%s elapsed_ms=%s",
        result.get("venue_id", venue.id),
        result.get("connected"),
        result.get("status_code"),
        elapsed_ms,
    )
    result["elapsed_ms"] = elapsed_ms
    return result
