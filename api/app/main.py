"""ProPresenter 원격 방송 API — FastAPI 진입점."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from app.bible import BibleStore, list_books
from app.config import Settings, get_settings, resolve_bible_path
from app.verse_service import VerseServiceError, parse_verse, send_verse
from app.presentations import PresentationsError, list_venue_presentations
from app.song_gateway import SongGatewayError, song_analyze, song_get_job
from app.venues import VenueError, VenueRegistry, probe_venue
from app.worship import WorshipError, worship_build, worship_build_song, worship_trigger

API_VERSION = "1.0.0"


class VerseRequest(BaseModel):
    reference: str = Field(..., examples=["요 3:16"])
    venue_id: str | None = Field(default=None, examples=["main"])


class WorshipBuildRequest(BaseModel):
    text: str = Field(..., examples=["마 3:1-10\n마 3:2"])


class WorshipTriggerRequest(BaseModel):
    index: int = Field(..., examples=[33])


class SongSection(BaseModel):
    type: str = Field(..., examples=["verse"])
    label: str = Field(..., examples=["1절"])
    lines: list[str] = Field(..., min_length=1, max_length=2)


class SongAnalyzeRequest(BaseModel):
    song_title: str = Field(..., alias="songTitle", examples=["주님의 마음"])
    image_base64: str | None = Field(default=None, alias="imageBase64")
    image_mime_type: str | None = Field(default=None, alias="imageMimeType")
    lyrics_text: str | None = Field(default=None, alias="lyricsText")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def require_image_or_lyrics(self) -> SongAnalyzeRequest:
        has_image = bool(self.image_base64 and self.image_mime_type)
        has_lyrics = bool(self.lyrics_text and self.lyrics_text.strip())
        if has_image == has_lyrics:
            raise ValueError(
                "imageBase64·imageMimeType 또는 lyricsText 중 하나만 제공해야 합니다."
            )
        return self


class WorshipBuildSongRequest(BaseModel):
    venue_id: str = Field(..., alias="venueId", examples=["main"])
    song_title: str = Field(..., alias="songTitle", examples=["주님의 마음"])
    build_mode: str = Field(default="append", alias="buildMode", examples=["append"])
    sections: list[SongSection]

    model_config = {"populate_by_name": True}


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
    app.state.settings = settings
    app.state.bible = BibleStore(bible_path)
    app.state.venues = VenueRegistry(settings.venues_json_path)
    yield


app = FastAPI(
    title="ProPresenter Live API",
    version=API_VERSION,
    description="성경 구절 파싱·2줄 분할·ProPresenter 송출 (1단계 MVP)",
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


@app.get("/health")
async def health() -> dict[str, Any]:
    bible: BibleStore = app.state.bible
    return {
        "status": "ok",
        "version": API_VERSION,
        "bible_path": str(bible.path),
        "bible_translation": bible.translation,
        "bible_verses_loaded": bible.verse_count,
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


@app.post("/api/v1/song/analyze")
async def api_song_analyze(
    body: SongAnalyzeRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    upstream_body: dict[str, Any] = {"songTitle": body.song_title}
    if body.lyrics_text:
        upstream_body["lyricsText"] = body.lyrics_text
    else:
        upstream_body["imageBase64"] = body.image_base64
        upstream_body["imageMimeType"] = body.image_mime_type
    try:
        return await song_analyze(settings, upstream_body)
    except SongGatewayError as exc:
        raise _http_from_song_gateway(exc) from exc


@app.get("/api/v1/song/jobs/{job_id}")
async def api_song_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        return await song_get_job(settings, job_id)
    except SongGatewayError as exc:
        raise _http_from_song_gateway(exc) from exc


@app.post("/api/v1/worship/build-song")
async def api_worship_build_song(
    body: WorshipBuildSongRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        venue = _get_venues().get(body.venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return await worship_build_song(
            venue,
            settings,
            song_title=body.song_title,
            build_mode=body.build_mode,
            sections=[s.model_dump() for s in body.sections],
        )
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


def _http_from_song_gateway(exc: SongGatewayError) -> HTTPException:
    detail: dict[str, Any] = {"message": str(exc)}
    if exc.hint:
        detail["hint"] = exc.hint
    return HTTPException(status_code=exc.status_code, detail=detail)
