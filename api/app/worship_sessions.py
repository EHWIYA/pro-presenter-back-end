"""WorshipSession 영속화."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorshipSession
from app.venue_runtime import update_runtime_from_build


class WorshipSessionError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _normalize_slide_map(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        if index is None:
            continue
        out.append(
            {
                "index": int(index),
                "label": str(item.get("label", "")),
                **({"preview": item["preview"]} if item.get("preview") else {}),
            }
        )
    return out


async def create_scripture_session(
    session: AsyncSession,
    venue_id: str,
    *,
    reference: str,
    agent_result: dict[str, Any],
) -> tuple[WorshipSession, dict[str, Any]]:
    slide_map = _normalize_slide_map(agent_result.get("slide_map") or agent_result.get("slideMap"))
    worship_session = WorshipSession(
        venue_id=venue_id,
        kind="scripture",
        reference=reference,
        slide_map=slide_map,
        slide_count=agent_result.get("slide_count"),
        total_slide_count=agent_result.get("total_slide_count"),
    )
    session.add(worship_session)
    await session.commit()
    await session.refresh(worship_session)

    await update_runtime_from_build(
        session,
        venue_id,
        session_id=worship_session.id,
        kind="scripture",
        reference=reference,
        slide_map=slide_map,
    )

    response = {
        **agent_result,
        "sessionId": str(worship_session.id),
        "reference": reference,
        "slide_map": slide_map,
    }
    return worship_session, response


async def get_session(
    session: AsyncSession,
    venue_id: str,
    session_id: uuid.UUID,
) -> WorshipSession:
    result = await session.execute(
        select(WorshipSession).where(
            WorshipSession.id == session_id,
            WorshipSession.venue_id == venue_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise WorshipSessionError("세션을 찾을 수 없습니다.", status_code=404)
    return row


async def record_trigger(
    session: AsyncSession,
    worship_session: WorshipSession,
    index: int,
) -> WorshipSession:
    worship_session.last_triggered_index = index
    worship_session.last_triggered_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(worship_session)
    return worship_session
