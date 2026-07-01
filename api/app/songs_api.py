"""곡 카탈로그 API — pro-presenter-data Libraries/*.pro."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, model_validator

from app.config import Settings, get_settings
from app.job_context import AnalyzeJobContext, get_job_context, set_job_context
from app.song_catalog import (
    SongCatalogError,
    find_by_title_normalized,
    get_catalog_song,
    get_song_detail,
    get_song_for_build,
    is_catalog_configured,
    library_candidates_response,
    library_hit_response,
    search_catalog,
    validate_section,
)
from app.song_gateway import SongGatewayError, song_analyze, song_get_job
from app.venues import VenueError
from app.worship import (
    WorshipError,
    fetch_song_sections_from_agent,
    worship_build_song,
)

router = APIRouter()

_GONE_DETAIL = (
    "곡 편집은 pro-presenter-data Git(Libraries/)에서 관리합니다. "
    "docs/handoff/song-catalog.md 참고."
)


@dataclass(frozen=True, slots=True)
class SectionsLoadResult:
    sections: list[dict[str, Any]]
    hint: str | None = None


def _format_agent_sections_hint(exc: WorshipError) -> str:
    msg = str(exc).strip()
    hint = (exc.hint or "").strip()
    if hint and hint not in msg:
        return f"{msg} ({hint})"
    return msg or hint or "에이전트에서 .pro 구간을 읽지 못했습니다."


class SongSection(BaseModel):
    type: str = Field(..., examples=["verse"])
    label: str = Field(..., examples=["1절"])
    lines: list[str] = Field(..., min_length=1)


class SongAnalyzeRequest(BaseModel):
    song_title: str | None = Field(
        default=None,
        alias="songTitle",
        description="선매칭·게이트웨이 힌트용.",
        examples=["주님의 마음"],
    )
    venue_id: str | None = Field(
        default=None,
        alias="venueId",
        description="선매칭 시 .pro sections 조회용 현장 ID.",
    )
    image_base64: str | None = Field(default=None, alias="imageBase64")
    image_mime_type: str | None = Field(default=None, alias="imageMimeType")
    lyrics_text: str | None = Field(default=None, alias="lyricsText")
    force_reanalyze: bool = Field(default=False, alias="forceReanalyze")
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
    library_category: str | None = Field(default=None, alias="libraryCategory")
    group_theme_key: str | None = Field(default=None, alias="groupThemeKey")
    lines_per_slide: int | None = Field(
        default=None,
        alias="linesPerSlide",
        ge=1,
        description="catalog 모드: 구간 lines 항목당 슬라이드 1줄 (최대 64줄/구간).",
    )
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


def _require_catalog(settings: Settings) -> None:
    if not is_catalog_configured(settings):
        raise HTTPException(
            status_code=503,
            detail="곡 카탈로그가 설정되지 않았습니다 (DATA_REPO_PATH/Libraries).",
        )


def _http_from_catalog(exc: SongCatalogError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _http_from_song_gateway(exc: SongGatewayError) -> HTTPException:
    detail: dict[str, Any] = {"message": str(exc)}
    if exc.hint:
        detail["hint"] = exc.hint
    return HTTPException(status_code=exc.status_code, detail=detail)


def _resolve_venue(request: Request, venue_id: str):
    try:
        return request.app.state.venues.get(venue_id)
    except VenueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _load_sections_for_song(
    request: Request,
    settings: Settings,
    *,
    venue_id: str | None,
    library_category: str,
    stem: str,
) -> SectionsLoadResult:
    if not venue_id:
        return SectionsLoadResult([])
    venue = _resolve_venue(request, venue_id)
    try:
        sections = await fetch_song_sections_from_agent(
            venue,
            settings,
            library_category=library_category,
            stem=stem,
        )
    except WorshipError as exc:
        return SectionsLoadResult([], hint=_format_agent_sections_hint(exc))
    return SectionsLoadResult(sections or [])


@router.get("/api/v1/songs")
async def list_songs(
    settings: Settings = Depends(get_settings),
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    library_category: str | None = Query(default=None, alias="libraryCategory"),
    limit: int = Query(default=0, ge=0, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_catalog(settings)
    eff_limit = limit or settings.song_catalog_default_limit
    try:
        items, total = search_catalog(
            settings,
            q=q,
            category=category,
            library_category=library_category,
            limit=eff_limit,
            offset=offset,
        )
    except SongCatalogError as exc:
        raise _http_from_catalog(exc) from exc
    return {"items": items, "total": total}


@router.get("/api/v1/songs/{song_id:path}")
async def get_song(
    song_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    venue_id: str | None = Query(default=None, alias="venueId"),
) -> dict[str, Any]:
    _require_catalog(settings)
    from app.song_catalog import parse_song_id

    try:
        lib_cat, stem = parse_song_id(song_id)
    except SongCatalogError as exc:
        raise _http_from_catalog(exc) from exc
    sections_list: list[dict[str, Any]] = []
    sections_hint: str | None = None
    if venue_id:
        loaded = await _load_sections_for_song(
            request,
            settings,
            venue_id=venue_id,
            library_category=lib_cat,
            stem=stem,
        )
        sections_list = loaded.sections
        sections_hint = loaded.hint
    detail = get_song_detail(settings, song_id, sections=sections_list)
    if detail is None:
        raise HTTPException(status_code=404, detail="곡을 찾을 수 없습니다.")
    if sections_hint:
        detail["sectionsHint"] = sections_hint
    elif venue_id and not sections_list:
        detail["sectionsHint"] = (
            "에이전트가 .pro 구간을 반환하지 않았습니다. "
            "GET /api/v1/venues/{venueId}/library/songs/{songId}/sections 확인."
        )
    return detail


@router.post("/api/v1/songs", status_code=410)
@router.patch("/api/v1/songs/{song_id:path}", status_code=410)
@router.delete("/api/v1/songs/{song_id:path}", status_code=410)
@router.put("/api/v1/songs/{song_id:path}/sections", status_code=410)
async def song_write_gone() -> dict[str, Any]:
    raise HTTPException(status_code=410, detail=_GONE_DETAIL)


@router.post("/api/v1/song/analyze")
async def api_song_analyze(
    body: SongAnalyzeRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    title_for_match = (body.song_title or "").strip()
    if is_catalog_configured(settings) and not body.force_reanalyze and title_for_match:
        matches = find_by_title_normalized(settings, title_for_match)
        if len(matches) == 1:
            sections: list[dict[str, Any]] | None = None
            if body.venue_id:
                loaded = await _load_sections_for_song(
                    request,
                    settings,
                    venue_id=body.venue_id,
                    library_category=matches[0].library_category,
                    stem=matches[0].stem,
                )
                sections = loaded.sections
            return library_hit_response(matches[0], sections=sections)
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
                save_to_library=False,
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
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        data = await song_get_job(settings, job_id)
    except SongGatewayError as exc:
        raise _http_from_song_gateway(exc) from exc

    status = str(data.get("status") or "")
    if status in ("finished", "completed"):
        data["libraryAction"] = "skipped"
        data["libraryReason"] = "data-repo"
        ctx = get_job_context(job_id)
        if ctx and ctx.library_song_id:
            data["librarySongId"] = ctx.library_song_id
    return data


@router.get("/api/v1/venues/{venue_id}/library/songs/{song_id:path}/sections")
async def venue_song_sections(
    venue_id: str,
    song_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _require_catalog(settings)
    from app.song_catalog import parse_song_id

    try:
        library_category, stem = parse_song_id(song_id)
    except SongCatalogError as exc:
        raise _http_from_catalog(exc) from exc
    if get_catalog_song(settings, song_id) is None:
        raise HTTPException(status_code=404, detail="곡을 찾을 수 없습니다.")
    venue = _resolve_venue(request, venue_id)
    try:
        sections = await fetch_song_sections_from_agent(
            venue,
            settings,
            library_category=library_category,
            stem=stem,
        )
    except WorshipError as exc:
        detail: dict[str, Any] = {"message": str(exc)}
        if exc.hint:
            detail["hint"] = exc.hint
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc
    return {
        "songId": song_id,
        "libraryCategory": library_category,
        "sections": sections,
    }


@router.post("/api/v1/worship/build-song")
async def api_worship_build_song(
    body: WorshipBuildSongRequest,
    request: Request,
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
    song_category: str | None = None

    if body.song_id:
        _require_catalog(settings)
        entry = get_song_for_build(settings, body.song_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="곡을 찾을 수 없습니다.")
        song_title = entry.title
        song_category = entry.category
        sections = await fetch_song_sections_from_agent(
            venue,
            settings,
            library_category=entry.library_category,
            stem=entry.stem,
        )
        if not sections:
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "에이전트에서 .pro 구간을 읽을 수 없습니다.",
                    "hint": (
                        "현장 에이전트에 GET /library/songs/{category}/{title}/sections "
                        "지원이 필요합니다. 신규 곡은 sections로 build-song 하세요."
                    ),
                },
            )
    else:
        sections = [s.model_dump() for s in (body.sections or [])]
        source_song_id = None
        for sec in sections:
            try:
                validate_section(sec, lines_per_slide=body.lines_per_slide)
            except SongCatalogError as exc:
                raise _http_from_catalog(exc) from exc

    from app.agent_library import AgentLibraryError, resolve_song_library_category

    try:
        library_category = resolve_song_library_category(
            song_title=song_title,
            song_category=song_category,
            override=body.library_category,
        )
    except AgentLibraryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    group_theme_key = (body.group_theme_key or "lyric").strip() or "lyric"

    try:
        result = await worship_build_song(
            venue,
            settings,
            song_title=song_title,
            build_mode=body.build_mode,
            sections=sections,
            library_category=library_category,
            source_song_id=source_song_id,
            group_theme_key=group_theme_key,
            lines_per_slide=body.lines_per_slide,
        )
    except WorshipError as exc:
        detail: dict[str, Any] = {"message": str(exc)}
        if exc.hint:
            detail["hint"] = exc.hint
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc

    if source_song_id:
        result["sourceSongId"] = source_song_id
    return result


@router.post("/api/v1/admin/songs/import", status_code=410)
async def admin_import_songs_gone() -> dict[str, Any]:
    raise HTTPException(status_code=410, detail=_GONE_DETAIL)
