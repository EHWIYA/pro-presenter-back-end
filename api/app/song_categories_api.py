"""카테고리 마스터 API 라우터."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session, is_db_configured
from app.song_categories import SongCategoriesError, create_category, delete_category, list_categories, update_category_label

router = APIRouter()


class SongCategoryCreateRequest(BaseModel):
    label: str = Field(..., examples=["주일 1부"])


class SongCategoryPatchRequest(BaseModel):
    label: str = Field(..., examples=["주일 예배 1부"])


def _require_db() -> None:
    if not is_db_configured():
        raise HTTPException(
            status_code=503,
            detail="곡 라이브러리 DB가 설정되지 않았습니다 (DATABASE_URL).",
        )


async def _db_session_required():
    _require_db()
    async for session in get_db_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(_db_session_required)]


def _http_from_categories(exc: SongCategoriesError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/api/v1/song-categories")
async def get_song_categories(session: DbSession) -> dict[str, Any]:
    return await list_categories(session)


@router.post("/api/v1/song-categories", status_code=201)
async def post_song_category(
    session: DbSession, body: SongCategoryCreateRequest
) -> dict[str, Any]:
    try:
        return await create_category(session, label=body.label)
    except SongCategoriesError as exc:
        raise _http_from_categories(exc) from exc


@router.patch("/api/v1/song-categories/{category_id}")
async def patch_song_category(
    session: DbSession, category_id: str, body: SongCategoryPatchRequest
) -> dict[str, Any]:
    try:
        return await update_category_label(session, category_id, label=body.label)
    except SongCategoriesError as exc:
        raise _http_from_categories(exc) from exc


@router.delete("/api/v1/song-categories/{category_id}")
async def delete_song_category(session: DbSession, category_id: str) -> dict[str, bool]:
    try:
        await delete_category(session, category_id)
    except SongCategoriesError as exc:
        raise _http_from_categories(exc) from exc
    return {"deleted": True}
