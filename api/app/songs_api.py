"""곡 라이브러리 API 라우터."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db_session, is_db_configured
from app.job_context import AnalyzeJobContext, set_job_context
from app.song_gateway import SongGatewayError, song_analyze, song_get_job
from app.song_library import (
    SongLibraryError,
    create_song,
    find_by_title_normalized,
    get_song_detail,
    get_song_for_build,
    import_song_record,
    library_candidates_response,
    library_hit_response,
    update_song_sections,
    search_songs,
    soft_delete_song,
    update_song_meta,
    upsert_from_analyze,
)
from app.venues import VenueError
from app.worship import WorshipError, worship_build_song

router = APIRouter()


class SongSection(BaseModel):
    type: str = Field(..., examples=["verse"])
    label: str = Field(..., examples=["1절"])
    lines: list[str] = Field(..., min_length=1, max_length=2)


class SongCreateRequest(BaseModel):
    title: str
    artist: str | None = None
    tags: list[str] = Field(default_factory=list)
    category: str | None = None
    sections: list[SongSection]


class SongPatchRequest(BaseModel):
    title: str | None = None
    artist: str | None = None
    tags: list[str] | None = None
    category: str | None = None


class SongSectionsUpdateRequest(BaseModel):
    sections: list[SongSection] | None = None
    title: str | None = None
    category: str | None = None


class SongAnalyzeRequest(BaseModel):
    song_title: str | None = Field(
        default=None,
        alias="songTitle",
        description="선매칭·게이트웨이 힌트용. 신규 악보(이미지만)는 생략 가능.",
        examples=["주님의 마음"],
    )
    image_base64: str | None = Field(default=None, alias="imageBase64")
    image_mime_type: str | None = Field(default=None, alias="imageMimeType")
    lyrics_text: str | None = Field(default=None, alias="lyricsText")
    force_reanalyze: bool = Field(default=False, alias="forceReanalyze")
    save_to_library: bool = Field(default=True, alias="saveToLibrary")
    library_song_id: str | None = Field(default=None, alias="librarySongId")
    client_ref: str | None = Field(default=None, alias="clientRef")

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
    venue_id: str = Field(..., alias="venueId", examples=["hwiya-pc"])
    song_title: str | None = Field(default=None, alias="songTitle")
    song_id: str | None = Field(default=None, alias="songId")
    build_mode: str = Field(default="replace", alias="buildMode", examples=["replace"])
    sections: list[SongSection] | None = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def song_id_xor_sections(self) -> WorshipBuildSongRequest:
        has_id = bool(self.song_id)
        has_sections = bool(self.sections)
        if has_id == has_sections:
            raise ValueError("songId 또는 sections 중 하나만 제공해야 합니다.")
        if has_sections and not self.song_title:
            raise ValueError("sections 경로에서는 songTitle이 필요합니다.")
        return self


def _require_db() -> None:
    if not is_db_configured():
        raise HTTPException(
            status_code=503,
            detail="곡 라이브러리 DB가 설정되지 않았습니다 (DATABASE_URL).",
        )


async def _db_session_required() -> AsyncGenerator[AsyncSession, None]:
    _require_db()
    async for session in get_db_session():
        yield session


async def _db_session_optional() -> AsyncGenerator[AsyncSession | None, None]:
    if not is_db_configured():
        yield None
        return
    async for session in get_db_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(_db_session_required)]
OptionalDbSession = Annotated[AsyncSession | None, Depends(_db_session_optional)]


def _http_from_library(exc: SongLibraryError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _http_from_song_gateway(exc: SongGatewayError) -> HTTPException:
    detail: dict[str, Any] = {"message": str(exc)}
    if exc.hint:
        detail["hint"] = exc.hint
    return HTTPException(status_code=exc.status_code, detail=detail)


def _require_admin_key(
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    if not settings.api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="유효하지 않은 API 키입니다.")


@router.get("/api/v1/songs")
async def list_songs(
    session: DbSession,
    settings: Settings = Depends(get_settings),
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=0, ge=0, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    eff_limit = limit or settings.song_library_default_limit
    try:
        items, total = await search_songs(
            session, q=q, category=category, limit=eff_limit, offset=offset
        )
    except SongLibraryError as exc:
        raise _http_from_library(exc) from exc
    return {"items": items, "total": total}


@router.get("/api/v1/songs/{song_id}")
async def get_song(session: DbSession, song_id: uuid.UUID) -> dict[str, Any]:
    detail = await get_song_detail(session, song_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="곡을 찾을 수 없습니다.")
    return detail


@router.post("/api/v1/songs", status_code=201)
async def post_song(session: DbSession, body: SongCreateRequest) -> dict[str, Any]:
    try:
        new_id = await create_song(
            session,
            title=body.title,
            artist=body.artist,
            tags=body.tags,
            category=body.category,
            sections=[s.model_dump() for s in body.sections],
        )
    except SongLibraryError as exc:
        raise _http_from_library(exc) from exc
    return {"songId": str(new_id)}


@router.patch("/api/v1/songs/{song_id}")
async def patch_song(
    session: DbSession, song_id: uuid.UUID, body: SongPatchRequest
) -> dict[str, Any]:
    try:
        ok = await update_song_meta(
            session,
            song_id,
            title=body.title,
            artist=body.artist,
            tags=body.tags,
            category=body.category,
        )
    except SongLibraryError as exc:
        raise _http_from_library(exc) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="곡을 찾을 수 없습니다.")
    return {"songId": str(song_id), "ok": True}


@router.delete("/api/v1/songs/{song_id}")
async def delete_song(session: DbSession, song_id: uuid.UUID) -> dict[str, Any]:
    ok = await soft_delete_song(session, song_id)
    if not ok:
        raise HTTPException(status_code=404, detail="곡을 찾을 수 없습니다.")
    return {"songId": str(song_id), "deleted": True}


@router.put("/api/v1/songs/{song_id}/sections")
async def put_song_sections(
    session: DbSession, song_id: uuid.UUID, body: SongSectionsUpdateRequest
) -> dict[str, Any]:
    sections = (
        [s.model_dump() for s in body.sections] if body.sections is not None else None
    )
    try:
        detail = await update_song_sections(
            session,
            song_id,
            sections=sections,
            title=body.title,
            category=body.category,
        )
    except SongLibraryError as exc:
        raise _http_from_library(exc) from exc
    if detail is None:
        raise HTTPException(status_code=404, detail="곡을 찾을 수 없습니다.")
    return {"ok": True, **detail}


@router.post("/api/v1/song/analyze")
async def api_song_analyze(
    body: SongAnalyzeRequest,
    response: Response,
    session: OptionalDbSession,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    title_for_match = (body.song_title or "").strip()
    if session is not None and not body.force_reanalyze and title_for_match:
        matches = await find_by_title_normalized(session, title_for_match)
        if len(matches) == 1:
            return library_hit_response(matches[0])
        if len(matches) > 1:
            return library_candidates_response(title_for_match, matches)

    upstream_body: dict[str, Any] = {}
    if title_for_match:
        upstream_body["songTitle"] = title_for_match
    input_kind = "lyrics"
    if body.lyrics_text:
        upstream_body["lyricsText"] = body.lyrics_text
    else:
        upstream_body["imageBase64"] = body.image_base64
        upstream_body["imageMimeType"] = body.image_mime_type
        input_kind = "image"
    if body.library_song_id:
        upstream_body["librarySongId"] = body.library_song_id
    if body.client_ref:
        upstream_body["clientRef"] = body.client_ref

    try:
        result = await song_analyze(settings, upstream_body)
    except SongGatewayError as exc:
        raise _http_from_song_gateway(exc) from exc

    job_id = str(result.get("jobId") or "")
    if job_id:
        set_job_context(
            job_id,
            AnalyzeJobContext(
                save_to_library=body.save_to_library,
                library_song_id=body.library_song_id,
                client_ref=body.client_ref,
                input_kind=input_kind,
            ),
        )
    response.status_code = 202
    return result


@router.get("/api/v1/song/jobs/{job_id}")
async def api_song_job(
    job_id: str,
    session: OptionalDbSession,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from app.job_context import get_job_context

    try:
        data = await song_get_job(settings, job_id)
    except SongGatewayError as exc:
        raise _http_from_song_gateway(exc) from exc

    status = str(data.get("status") or "")
    ctx = get_job_context(job_id)
    save_to_library = ctx.save_to_library if ctx else settings.song_library_auto_save

    if status in ("finished", "completed") and save_to_library and session is not None:
        parsed = data.get("parsed") or {}
        sections = parsed.get("sections") or []
        title = (
            parsed.get("song_title")
            or parsed.get("songTitle")
            or data.get("songTitle")
            or ""
        )
        if title and sections:
            library_song_id = (ctx.library_song_id if ctx else None) or data.get(
                "librarySongId"
            )
            try:
                song_uuid, action = await upsert_from_analyze(
                    session,
                    title=str(title),
                    sections=sections,
                    library_song_id=str(library_song_id) if library_song_id else None,
                    source_job_id=job_id,
                    input_kind=ctx.input_kind if ctx else None,
                    client_ref=ctx.client_ref if ctx else None,
                )
                data["songId"] = str(song_uuid)
                data["libraryAction"] = action
            except SongLibraryError as exc:
                data["libraryAction"] = "skipped"
                data["libraryError"] = str(exc)
        else:
            data["libraryAction"] = "skipped"
    elif status in ("finished", "completed"):
        data["libraryAction"] = "skipped"

    return data


@router.post("/api/v1/worship/build-song")
async def api_worship_build_song(
    body: WorshipBuildSongRequest,
    request: Request,
    session: OptionalDbSession,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    venues = request.app.state.venues
    try:
        venue = venues.get(body.venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    song_title = body.song_title or ""
    sections: list[dict[str, Any]]
    source_song_id: str | None = body.song_id

    if body.song_id:
        if session is None:
            raise HTTPException(
                status_code=503,
                detail="songId 경로는 DATABASE_URL 설정이 필요합니다.",
            )
        try:
            uid = uuid.UUID(body.song_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="songId 형식이 올바르지 않습니다.") from exc
        loaded = await get_song_for_build(session, uid)
        if loaded is None:
            raise HTTPException(status_code=404, detail="곡을 찾을 수 없습니다.")
        song_title, sections = loaded
    else:
        sections = [s.model_dump() for s in (body.sections or [])]
        source_song_id = None

    try:
        result = await worship_build_song(
            venue,
            settings,
            song_title=song_title,
            build_mode=body.build_mode,
            sections=sections,
            source_song_id=source_song_id,
        )
    except WorshipError as exc:
        detail: dict[str, Any] = {"message": str(exc)}
        if exc.hint:
            detail["hint"] = exc.hint
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc

    if source_song_id:
        result["sourceSongId"] = source_song_id
    return result


@router.post(
    "/api/v1/admin/songs/import",
    dependencies=[Depends(_require_admin_key)],
)
async def admin_import_songs(session: DbSession, request: Request) -> dict[str, Any]:
    raw = await request.body()
    if not raw.strip():
        raise HTTPException(status_code=400, detail="import body가 비어 있습니다.")
    created = updated = errors = 0
    error_lines: list[str] = []
    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            _, action = await import_song_record(session, record)
            if action == "created":
                created += 1
            else:
                updated += 1
        except (json.JSONDecodeError, SongLibraryError) as exc:
            errors += 1
            error_lines.append(f"line {line_no}: {exc}")
    return {
        "created": created,
        "updated": updated,
        "errors": errors,
        "errorLines": error_lines[:20],
    }
