"""pro-presenter-data Libraries/*.pro 곡 카탈로그 (read-only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from app.agent_library import SONG_LIBRARY_CATEGORIES
from app.config import Settings
from app.data_repo import file_mtime_iso, libraries_root, read_git_revision, resolve_data_repo_path
from app.title_normalize import normalize_song_title

SECTION_TYPES = frozenset(
    {
        "title",
        "intro",
        "verse",
        "pre_chorus",
        "chorus",
        "bridge",
        "tag",
        "outro",
        "instrumental",
        "unknown",
    }
)

MAX_SECTION_LINES_LEGACY = 2
MAX_SECTION_LINES_CATALOG = 64

FOLDER_TO_API_CATEGORY: dict[str, str] = {
    "찬양": "praise",
    "찬송가": "hymnal",
    "성가곡": "hymn",
}

API_CATEGORY_TO_FOLDERS: dict[str, frozenset[str]] = {
    "praise": frozenset({"찬양"}),
    "special": frozenset({"찬양"}),
    "hymn": frozenset({"성가곡"}),
    "hymnal": frozenset({"찬송가"}),
}


class SongCatalogError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class CatalogSong:
    song_id: str
    title: str
    library_category: str
    category: str
    presentation_filename: str
    updated_at: str

    @property
    def stem(self) -> str:
        return self.title


def is_catalog_configured(settings: Settings) -> bool:
    root = libraries_root(settings)
    return root.is_dir()


def encode_song_id(library_category: str, stem: str) -> str:
    return f"{library_category}/{stem}"


def parse_song_id(song_id: str) -> tuple[str, str]:
    decoded = unquote(song_id.strip())
    if "/" not in decoded:
        raise SongCatalogError("songId는 {library_category}/{제목} 형식이어야 합니다.", status_code=422)
    library_category, stem = decoded.split("/", 1)
    library_category = library_category.strip()
    stem = stem.strip()
    if not library_category or not stem:
        raise SongCatalogError("songId가 비어 있습니다.", status_code=422)
    if library_category not in SONG_LIBRARY_CATEGORIES:
        raise SongCatalogError(
            f"library_category는 {', '.join(sorted(SONG_LIBRARY_CATEGORIES))} 중 하나여야 합니다.",
            status_code=422,
        )
    return library_category, stem


def _scan_folder(library_category: str, folder: Path) -> list[CatalogSong]:
    if not folder.is_dir():
        return []
    api_category = FOLDER_TO_API_CATEGORY.get(library_category, "praise")
    items: list[CatalogSong] = []
    for path in sorted(folder.glob("*.pro")):
        if not path.is_file():
            continue
        stem = path.stem
        items.append(
            CatalogSong(
                song_id=encode_song_id(library_category, stem),
                title=stem,
                library_category=library_category,
                category=api_category,
                presentation_filename=path.name,
                updated_at=file_mtime_iso(path),
            )
        )
    return items


def load_catalog(settings: Settings) -> list[CatalogSong]:
    root = libraries_root(settings)
    if not root.is_dir():
        return []
    songs: list[CatalogSong] = []
    for library_category in sorted(SONG_LIBRARY_CATEGORIES):
        songs.extend(_scan_folder(library_category, root / library_category))
    return songs


def _match_query(song: CatalogSong, q: str | None) -> bool:
    if not q or not q.strip():
        return True
    needle = normalize_song_title(q)
    if not needle:
        return True
    return needle in normalize_song_title(song.title)


def _match_category(song: CatalogSong, category: str | None, library_category: str | None) -> bool:
    if library_category and library_category.strip():
        return song.library_category == library_category.strip()
    if not category or not category.strip():
        return True
    cat = category.strip()
    folders = API_CATEGORY_TO_FOLDERS.get(cat)
    if folders is None:
        raise SongCatalogError(
            "category는 praise, hymn, hymnal, special 또는 libraryCategory를 사용하세요.",
            status_code=422,
        )
    return song.library_category in folders


def search_catalog(
    settings: Settings,
    *,
    q: str | None = None,
    category: str | None = None,
    library_category: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    catalog = load_catalog(settings)
    filtered = [
        song
        for song in catalog
        if _match_query(song, q) and _match_category(song, category, library_category)
    ]
    total = len(filtered)
    page = filtered[offset : offset + limit]
    return [_song_summary(song) for song in page], total


def get_catalog_song(settings: Settings, song_id: str) -> CatalogSong | None:
    try:
        library_category, stem = parse_song_id(song_id)
    except SongCatalogError:
        return None
    path = libraries_root(settings) / library_category / f"{stem}.pro"
    if not path.is_file():
        return None
    api_category = FOLDER_TO_API_CATEGORY.get(library_category, "praise")
    return CatalogSong(
        song_id=encode_song_id(library_category, stem),
        title=stem,
        library_category=library_category,
        category=api_category,
        presentation_filename=path.name,
        updated_at=file_mtime_iso(path),
    )


def find_by_title_normalized(settings: Settings, title: str) -> list[CatalogSong]:
    needle = normalize_song_title(title)
    if not needle:
        return []
    return [
        song
        for song in load_catalog(settings)
        if normalize_song_title(song.title) == needle
    ]


def get_song_detail(
    settings: Settings,
    song_id: str,
    *,
    sections: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    song = get_catalog_song(settings, song_id)
    if song is None:
        return None
    sec = sections if sections is not None else []
    return {
        "songId": song.song_id,
        "title": song.title,
        "artist": None,
        "tags": [],
        "category": song.category,
        "libraryCategory": song.library_category,
        "presentationFilename": song.presentation_filename,
        "sections": sec,
        "sectionCount": len(sec),
        "updatedAt": song.updated_at,
        "source": "data-repo",
    }


def get_song_for_build(settings: Settings, song_id: str) -> CatalogSong | None:
    return get_catalog_song(settings, song_id)


def catalog_status(settings: Settings) -> dict[str, Any]:
    repo_path = resolve_data_repo_path(settings)
    configured = is_catalog_configured(settings)
    count = len(load_catalog(settings)) if configured else 0
    return {
        "source": "data-repo",
        "configured": configured,
        "path": str(repo_path),
        "revision": read_git_revision(repo_path),
        "count": count,
    }


def _song_summary(song: CatalogSong) -> dict[str, Any]:
    return {
        "songId": song.song_id,
        "title": song.title,
        "artist": None,
        "tags": [],
        "category": song.category,
        "libraryCategory": song.library_category,
        "presentationFilename": song.presentation_filename,
        "sectionCount": None,
        "updatedAt": song.updated_at,
    }


def library_hit_response(song: CatalogSong, *, sections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sec = sections if sections is not None else []
    return {
        "source": "library",
        "songId": song.song_id,
        "title": song.title,
        "category": song.category,
        "libraryCategory": song.library_category,
        "sections": sec,
        "schemaVersion": "song-sections/v1",
    }


def library_candidates_response(title: str, songs: list[CatalogSong]) -> dict[str, Any]:
    return {
        "source": "library_candidates",
        "query": title,
        "candidates": [_song_summary(s) for s in songs],
    }


def validate_section(section: dict[str, Any], *, lines_per_slide: int | None = None) -> None:
    stype = section.get("type")
    if stype not in SECTION_TYPES:
        raise SongCatalogError(f"유효하지 않은 section type: {stype}", status_code=422)
    label = section.get("label")
    if not label or not str(label).strip():
        raise SongCatalogError("section label이 필요합니다.", status_code=422)
    lines = section.get("lines")
    max_lines = MAX_SECTION_LINES_CATALOG if lines_per_slide is not None else MAX_SECTION_LINES_LEGACY
    if not isinstance(lines, list) or not lines or len(lines) > max_lines:
        if lines_per_slide is not None:
            raise SongCatalogError(
                f"section lines는 1~{MAX_SECTION_LINES_CATALOG}줄이어야 합니다.",
                status_code=422,
            )
        raise SongCatalogError("section lines는 1~2줄이어야 합니다.", status_code=422)
