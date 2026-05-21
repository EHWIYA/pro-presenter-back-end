"""성경 파싱 + (선택) ProPresenter 송출."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.bible import BibleError, BibleStore
from app.config import Settings
from app.propresenter import ProPresenterClient, ProPresenterError
from app.split import format_verse
from app.venues import Venue, VenueError, VenueRegistry, pp_ids_for_venue

DEFAULT_THEME_SLIDE_UUID = "0cdbd9c6-7ffd-45dc-8bef-fce91f8d9202"


async def parse_verse(
    bible: BibleStore,
    reference: str,
) -> dict[str, Any]:
    try:
        verse = bible.lookup(reference)
    except BibleError as exc:
        raise VerseServiceError(str(exc), status_code=400) from exc

    title, lines, raw = format_verse(verse.title, verse.body)
    return {
        "reference": verse.reference,
        "title": title,
        "lines": lines,
        "raw_text": raw,
        "book": verse.book_name,
        "chapter": verse.chapter,
        "verse": verse.verse,
    }


async def send_verse(
    bible: BibleStore,
    venues: VenueRegistry,
    settings: Settings,
    reference: str,
    venue_id: str,
) -> dict[str, Any]:
    parsed = await parse_verse(bible, reference)
    try:
        venue = venues.get(venue_id)
    except VenueError as exc:
        raise VerseServiceError(str(exc), status_code=404) from exc

    pp_ids = pp_ids_for_venue(venue, settings)
    method = (settings.pp_send_method or "theme").strip().lower()
    client = ProPresenterClient(venue, settings.pp_http_timeout_sec)

    pp_warning: str | None = None
    pp_dynamic = True

    try:
        if method == "message":
            message_id = pp_ids.get("message_id")
            if not message_id:
                raise VerseServiceError(
                    "메시지 송출용 PP_MESSAGE_ID가 설정되지 않았습니다.",
                    status_code=500,
                )
            await client.send_verse_message(
                message_id,
                parsed["title"],
                parsed["lines"],
            )
        else:
            theme_slide_id = pp_ids.get("theme_slide_id") or DEFAULT_THEME_SLIDE_UUID
            await client.send_verse_theme(
                pp_ids.get("theme_id"),
                theme_slide_id,
                parsed["title"],
                parsed["lines"],
                library_id=pp_ids.get("library_id"),
                presentation_id=pp_ids.get("presentation_id"),
                slide_uuid=DEFAULT_THEME_SLIDE_UUID,
            )
    except ProPresenterError as exc:
        lib = pp_ids.get("library_id")
        pres = pp_ids.get("presentation_id")
        if method == "theme" and lib and pres:
            await client.trigger_library_presentation(lib, pres)
            pp_dynamic = False
            pp_warning = (
                f"테마 슬라이드 텍스트 갱신 실패, test 프레젠테이션만 트리거했습니다: {exc}"
            )
        else:
            raise VerseServiceError(
                str(exc),
                status_code=502 if (exc.status_code or 0) >= 500 else 503,
                hint=exc.hint,
            ) from exc

    result = {
        **parsed,
        "venue_id": venue_id,
        "pp_triggered": True,
        "pp_send_method": method,
        "pp_dynamic_text": pp_dynamic,
    }
    if pp_warning:
        result["pp_warning"] = pp_warning
    _append_send_log(settings.send_log_path, result)
    return result


def _append_send_log(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class VerseServiceError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, hint: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.hint = hint
