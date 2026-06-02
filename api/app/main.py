"""ProPresenter 원격 방송 API — FastAPI 진입점."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.bible import BibleStore, list_books
from app.config import Settings, get_settings, resolve_bible_path
from app.database import dispose_db, ensure_schema, init_db, is_db_configured
from app.songs_api import router as songs_router
from app.verse_service import VerseServiceError, parse_verse, send_verse
from app.presentations import PresentationsError, list_venue_presentations
from app.venues import VenueError, VenueRegistry, probe_venue
from app.worship import WorshipError, worship_build, worship_trigger

API_VERSION = "1.1.0"


class VerseRequest(BaseModel):
    reference: str = Field(..., examples=["요 3:16"])
    venue_id: str | None = Field(default=None, examples=["main"])


class WorshipBuildRequest(BaseModel):
    text: str = Field(..., examples=["마 3:1-10\n마 3:2"])


class WorshipTriggerRequest(BaseModel):
    index: int = Field(..., examples=[33])


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


@app.get("/health")
async def health() -> dict[str, Any]:
    bible: BibleStore = app.state.bible
    return {
        "status": "ok",
        "version": API_VERSION,
        "bible_path": str(bible.path),
        "bible_translation": bible.translation,
        "bible_verses_loaded": bible.verse_count,
        "song_library_db": is_db_configured(),
    }


@app.get("/api/v1/books")
async def books() -> dict[str, Any]:
    return {"books": list_books()}


@app.get("/venues")
async def list_venues() -> dict[str, Any]:
    return {"venues": _get_venues().list_public()}


@app.get("/venues/{venue_id}/probe")
async def venue_probe(
    venue_id: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        venue = _get_venues().get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await probe_venue(venue, settings.pp_http_timeout_sec)


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


@app.post("/venues/{venue_id}/worship/build")
async def venue_worship_build(
    venue_id: str,
    body: WorshipBuildRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        venue = _get_venues().get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return await worship_build(venue, settings, body.text)
    except WorshipError as exc:
        raise _http_from_worship(exc) from exc


@app.post("/venues/{venue_id}/worship/trigger")
async def venue_worship_trigger(
    venue_id: str,
    body: WorshipTriggerRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        venue = _get_venues().get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return await worship_trigger(venue, settings, body.index)
    except WorshipError as exc:
        raise _http_from_worship(exc) from exc


@app.post("/api/v1/verse/parse", dependencies=[Depends(_require_api_key)])
async def verse_parse(body: VerseRequest) -> dict[str, Any]:
    try:
        return await parse_verse(_get_bible(), body.reference)
    except VerseServiceError as exc:
        raise _http_from_service(exc) from exc


@app.post("/api/v1/verse/send", dependencies=[Depends(_require_api_key)])
async def verse_send(body: VerseRequest) -> dict[str, Any]:
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
