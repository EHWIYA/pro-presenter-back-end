"""venue runtime · worship session ORM."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")


class VenueRuntime(Base):
    """현장 heartbeat·빌드 캐시 (venue_id PK)."""

    __tablename__ = "venue_runtime"

    venue_id: Mapped[str] = mapped_column(Text, primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    pp_reachable: Mapped[bool | None] = mapped_column(nullable=True)
    pp_current_presentation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    pp_current_slide_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pp_preview_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_reachable: Mapped[bool | None] = mapped_column(nullable=True)
    agent_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    data_git_revision: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_reported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_build_session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    last_build_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_build_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_build_slide_map: Mapped[list | None] = mapped_column(JsonType, nullable=True)
    last_build_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorshipSession(Base):
    """말씀·찬양 빌드 세션 (slide_map 영속)."""

    __tablename__ = "worship_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="scripture")
    reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    presentation_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    library_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    slide_map: Mapped[list] = mapped_column(JsonType, nullable=False, server_default="[]")
    slide_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_slide_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_triggered_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
