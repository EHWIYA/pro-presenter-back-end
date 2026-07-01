"""곡 라이브러리 CRUD · 검색 · analyze upsert."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import SECTION_TYPES, Song, SongSection, SongSource
from app.song_category import (
    DEFAULT_CATEGORY,
    SongCategoryError,
    normalize_category,
    validate_category,
)
from app.song_categories import custom_category_exists


def _coerce_category(value: str) -> str:
    try:
        return validate_category(value)
    except SongCategoryError as exc:
        raise SongLibraryError(str(exc), status_code=422) from exc


async def _coerce_category_registered(session: AsyncSession, value: str) -> str:
    category = _coerce_category(value)
    if category.startswith("custom:") and not await custom_category_exists(
        session, category
    ):
        raise SongLibraryError(
            f"등록되지 않은 category입니다: {category}",
            status_code=422,
        )
    return category
from app.title_normalize import normalize_song_title


class SongLibraryError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _validate_section(section: dict[str, Any]) -> None:
    stype = section.get("type")
    if stype not in SECTION_TYPES:
        raise SongLibraryError(f"유효하지 않은 section type: {stype}")
    label = section.get("label")
    if not label or not str(label).strip():
        raise SongLibraryError("section label이 필요합니다.")
    lines = section.get("lines")
    if not isinstance(lines, list) or not lines or len(lines) > 2:
        raise SongLibraryError("section lines는 1~2줄이어야 합니다.")


def _section_dict(section: SongSection) -> dict[str, Any]:
    return {"type": section.type, "label": section.label, "lines": section.lines}


def _song_category(song: Song) -> str:
    return song.category or DEFAULT_CATEGORY


def _song_summary(song: Song) -> dict[str, Any]:
    return {
        "songId": str(song.id),
        "title": song.title,
        "artist": song.artist,
        "tags": song.tags or [],
        "category": _song_category(song),
        "sectionCount": len(song.sections),
        "updatedAt": song.updated_at.isoformat(),
    }


async def search_songs(
    session: AsyncSession,
    *,
    q: str | None = None,
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    base = (
        select(Song)
        .options(selectinload(Song.sections))
        .where(Song.deleted_at.is_(None))
    )
    if category is not None and category.strip():
        cat = _coerce_category(category.strip())
        base = base.where(Song.category == cat)
    if q and q.strip():
        q_norm = normalize_song_title(q)
        pattern = f"%{q.strip()}%"
        base = base.where(
            or_(
                Song.title.ilike(pattern),
                Song.title_normalized == q_norm,
            )
        )
    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.scalar(count_stmt)) or 0)
    stmt = base.order_by(Song.updated_at.desc()).limit(limit).offset(offset)
    songs = (await session.scalars(stmt)).all()
    return [_song_summary(s) for s in songs], total


async def get_song_detail(session: AsyncSession, song_id: uuid.UUID) -> dict[str, Any] | None:
    stmt = (
        select(Song)
        .options(selectinload(Song.sections))
        .where(Song.id == song_id, Song.deleted_at.is_(None))
    )
    song = await session.scalar(stmt)
    if song is None:
        return None
    return {
        "songId": str(song.id),
        "title": song.title,
        "artist": song.artist,
        "tags": song.tags or [],
        "category": _song_category(song),
        "sections": [_section_dict(s) for s in song.sections],
        "sectionCount": len(song.sections),
        "createdAt": song.created_at.isoformat(),
        "updatedAt": song.updated_at.isoformat(),
    }


async def find_by_title_normalized(
    session: AsyncSession, title: str
) -> list[Song]:
    norm = normalize_song_title(title)
    if not norm:
        return []
    stmt = (
        select(Song)
        .options(selectinload(Song.sections))
        .where(Song.title_normalized == norm, Song.deleted_at.is_(None))
        .order_by(Song.updated_at.desc())
    )
    return list((await session.scalars(stmt)).all())


async def create_song(
    session: AsyncSession,
    *,
    title: str,
    artist: str | None,
    tags: list[str],
    sections: list[dict[str, Any]],
    category: str | None = None,
) -> uuid.UUID:
    if not title.strip():
        raise SongLibraryError("title이 필요합니다.")
    for sec in sections:
        _validate_section(sec)
    now = datetime.now(UTC)
    song = Song(
        title=title.strip(),
        title_normalized=normalize_song_title(title),
        artist=artist,
        tags=tags,
        category=(
            await _coerce_category_registered(session, category)
            if category is not None and str(category).strip()
            else DEFAULT_CATEGORY
        ),
        created_at=now,
        updated_at=now,
    )
    session.add(song)
    await session.flush()
    await _replace_sections_on_song(session, song, sections)
    await session.commit()
    return song.id


async def update_song_meta(
    session: AsyncSession,
    song_id: uuid.UUID,
    *,
    title: str | None = None,
    artist: str | None = None,
    tags: list[str] | None = None,
    category: str | None = None,
) -> bool:
    song = await _get_active_song(session, song_id)
    if song is None:
        return False
    if title is not None:
        song.title = title.strip()
        song.title_normalized = normalize_song_title(title)
    if artist is not None:
        song.artist = artist
    if tags is not None:
        song.tags = tags
    if category is not None:
        song.category = await _coerce_category_registered(session, category)
    song.updated_at = datetime.now(UTC)
    await session.commit()
    return True


async def soft_delete_song(session: AsyncSession, song_id: uuid.UUID) -> bool:
    song = await _get_active_song(session, song_id)
    if song is None:
        return False
    song.deleted_at = datetime.now(UTC)
    await session.commit()
    return True


async def update_song_sections(
    session: AsyncSession,
    song_id: uuid.UUID,
    *,
    sections: list[dict[str, Any]] | None = None,
    title: str | None = None,
    category: str | None = None,
) -> dict[str, Any] | None:
    """sections·title·category 부분 갱신. sections 생략·빈 배열이면 기존 구간 유지."""
    song = await _get_active_song(session, song_id, load_sections=True)
    if song is None:
        return None
    if title is not None:
        if not title.strip():
            raise SongLibraryError("title이 비어 있을 수 없습니다.")
        song.title = title.strip()
        song.title_normalized = normalize_song_title(title)
    if category is not None:
        song.category = await _coerce_category_registered(session, category)
    if sections:
        for sec in sections:
            _validate_section(sec)
        await _replace_sections_on_song(session, song, sections)
    song.updated_at = datetime.now(UTC)
    await session.commit()
    session.expire_all()
    return await get_song_detail(session, song_id)


async def upsert_from_analyze(
    session: AsyncSession,
    *,
    title: str,
    sections: list[dict[str, Any]],
    library_song_id: str | None = None,
    source_job_id: str | None = None,
    input_kind: str | None = None,
    client_ref: str | None = None,
) -> tuple[uuid.UUID, str]:
    for sec in sections:
        _validate_section(sec)
    now = datetime.now(UTC)
    song: Song | None = None
    action = "created"

    if library_song_id:
        try:
            uid = uuid.UUID(library_song_id)
        except ValueError as exc:
            raise SongLibraryError("librarySongId 형식이 올바르지 않습니다.") from exc
        song = await _get_active_song(session, uid, load_sections=True)
        if song is None:
            raise SongLibraryError("librarySongId에 해당하는 곡이 없습니다.", status_code=404)
        action = "updated"
    else:
        matches = await find_by_title_normalized(session, title)
        if len(matches) == 1:
            song = matches[0]
            action = "updated"

    if song is None:
        song = Song(
            title=title.strip(),
            title_normalized=normalize_song_title(title),
            created_at=now,
            updated_at=now,
        )
        session.add(song)
        await session.flush()
    else:
        song.title = title.strip()
        song.title_normalized = normalize_song_title(title)
        song.updated_at = now

    await _replace_sections_on_song(session, song, sections)
    session.add(
        SongSource(
            song_id=song.id,
            source_type="ai_analyze",
            source_job_id=source_job_id,
            input_kind=input_kind,
            client_ref=client_ref,
        )
    )
    await session.commit()
    return song.id, action


async def import_song_record(
    session: AsyncSession,
    record: dict[str, Any],
) -> tuple[uuid.UUID, str]:
    """NDJSON import — sourceJobId 기준 idempotent upsert."""
    source_job_id = record.get("sourceJobId") or record.get("source_job_id")
    title = record.get("title") or record.get("songTitle") or ""
    sections = record.get("sections") or []
    if not title.strip():
        raise SongLibraryError("import record에 title이 없습니다.")
    if source_job_id:
        existing = await session.scalar(
            select(Song)
            .join(SongSource)
            .options(selectinload(Song.sections))
            .where(SongSource.source_job_id == source_job_id, Song.deleted_at.is_(None))
        )
        if existing:
            existing.title = title.strip()
            existing.title_normalized = normalize_song_title(title)
            await _replace_sections_on_song(session, existing, sections)
            existing.updated_at = datetime.now(UTC)
            await session.commit()
            return existing.id, "updated"
    song_id, action = await upsert_from_analyze(
        session,
        title=title,
        sections=sections,
        source_job_id=source_job_id,
        input_kind=record.get("inputKind") or record.get("input_kind"),
        client_ref=record.get("clientRef") or record.get("client_ref"),
    )
    return song_id, action


async def get_song_for_build(
    session: AsyncSession, song_id: uuid.UUID
) -> tuple[str, list[dict[str, Any]], str] | None:
    song = await _get_active_song(session, song_id, load_sections=True)
    if song is None:
        return None
    sections = [_section_dict(s) for s in song.sections]
    return song.title, sections, _song_category(song)


async def _get_active_song(
    session: AsyncSession,
    song_id: uuid.UUID,
    *,
    load_sections: bool = False,
) -> Song | None:
    stmt = select(Song).where(Song.id == song_id, Song.deleted_at.is_(None))
    if load_sections:
        stmt = stmt.options(selectinload(Song.sections))
    return await session.scalar(stmt)


async def _replace_sections_on_song(
    session: AsyncSession, song: Song, sections: list[dict[str, Any]]
) -> None:
    if song.id is not None:
        await session.execute(delete(SongSection).where(SongSection.song_id == song.id))
    for idx, sec in enumerate(sections):
        session.add(
            SongSection(
                song_id=song.id,
                sort_order=idx,
                type=sec["type"],
                label=sec["label"],
                lines=sec["lines"],
            )
        )


def library_hit_response(song: Song) -> dict[str, Any]:
    return {
        "source": "library",
        "songId": str(song.id),
        "title": song.title,
        "category": _song_category(song),
        "sections": [_section_dict(s) for s in song.sections],
        "schemaVersion": "song-sections/v1",
    }


def library_candidates_response(title: str, songs: list[Song]) -> dict[str, Any]:
    return {
        "source": "library_candidates",
        "query": title,
        "candidates": [_song_summary(s) for s in songs],
    }
