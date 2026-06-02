"""SQLAlchemy 2 async engine · session."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.config import Settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_current_url: str | None = None


def init_db(settings: Settings) -> None:
    global _engine, _session_factory, _current_url
    url = (settings.database_url or "").strip()
    if not url:
        _engine = None
        _session_factory = None
        _current_url = None
        return
    if _current_url == url and _engine is not None:
        return
    kwargs: dict = {"pool_pre_ping": True}
    if ":memory:" in url or url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    _engine = create_async_engine(url, **kwargs)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    _current_url = url


def is_db_configured() -> bool:
    return _session_factory is not None


def get_engine():
    return _engine


async def ensure_schema() -> None:
    """테스트용 SQLite — Alembic 없이 metadata create."""
    if _engine is None:
        return
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    global _engine, _session_factory, _current_url
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    _current_url = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다.")
    async with _session_factory() as session:
        yield session
