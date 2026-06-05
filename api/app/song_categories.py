"""카테고리 마스터 CRUD."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Song, SongCategoryMaster
from app.song_category import (
    BUILTIN_CATEGORY_IDS,
    SongCategoryError,
    is_builtin_category_id,
    make_custom_category_id,
    validate_category_label,
)


class SongCategoriesError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        detail: str | dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail if detail is not None else message


def _category_dict(row: SongCategoryMaster) -> dict[str, Any]:
    return {
        "id": row.id,
        "label": row.label,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


async def list_categories(session: AsyncSession) -> dict[str, Any]:
    stmt = select(SongCategoryMaster).order_by(
        SongCategoryMaster.created_at.asc(),
        SongCategoryMaster.label.asc(),
    )
    rows = (await session.scalars(stmt)).all()
    return {
        "builtin": list(BUILTIN_CATEGORY_IDS),
        "custom": [_category_dict(r) for r in rows],
    }


async def create_category(session: AsyncSession, *, label: str) -> dict[str, Any]:
    try:
        normalized = validate_category_label(label)
        category_id = make_custom_category_id(normalized)
    except SongCategoryError as exc:
        raise SongCategoriesError(str(exc), status_code=422) from exc

    existing = await session.get(SongCategoryMaster, category_id)
    if existing is not None:
        raise SongCategoriesError(
            "이미 존재하는 카테고리입니다.",
            status_code=409,
            detail="category_exists",
        )

    now = datetime.now(UTC)
    row = SongCategoryMaster(
        id=category_id,
        label=normalized,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _category_dict(row)


async def update_category_label(
    session: AsyncSession, category_id: str, *, label: str
) -> dict[str, Any]:
    if is_builtin_category_id(category_id):
        raise SongCategoriesError("기본 카테고리는 수정할 수 없습니다.", status_code=404)

    row = await session.get(SongCategoryMaster, category_id)
    if row is None:
        raise SongCategoriesError("카테고리를 찾을 수 없습니다.", status_code=404)

    try:
        normalized = validate_category_label(label)
    except SongCategoryError as exc:
        raise SongCategoriesError(str(exc), status_code=422) from exc

    row.label = normalized
    row.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return _category_dict(row)


async def delete_category(session: AsyncSession, category_id: str) -> None:
    if is_builtin_category_id(category_id):
        raise SongCategoriesError("기본 카테고리는 삭제할 수 없습니다.", status_code=404)

    row = await session.get(SongCategoryMaster, category_id)
    if row is None:
        raise SongCategoriesError("카테고리를 찾을 수 없습니다.", status_code=404)

    count_stmt = (
        select(func.count())
        .select_from(Song)
        .where(Song.category == category_id, Song.deleted_at.is_(None))
    )
    song_count = int((await session.scalar(count_stmt)) or 0)
    if song_count > 0:
        raise SongCategoriesError(
            "이 카테고리를 사용하는 곡이 있습니다.",
            status_code=409,
            detail={
                "detail": "category_in_use",
                "message": "이 카테고리를 사용하는 곡이 있습니다.",
                "songCount": song_count,
            },
        )

    await session.execute(
        delete(SongCategoryMaster).where(SongCategoryMaster.id == category_id)
    )
    await session.commit()


async def custom_category_exists(session: AsyncSession, category_id: str) -> bool:
    if not category_id.startswith("custom:"):
        return True
    row = await session.get(SongCategoryMaster, category_id)
    return row is not None
