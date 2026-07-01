"""drop song library tables — catalog moved to pro-presenter-data

Revision ID: 006_drop_song_library
Revises: 005_worship_session_library_target
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op

revision = "006_drop_song_library"
down_revision = "005_worship_session_library_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("song_sources")
    op.drop_table("song_sections")
    op.drop_table("songs")
    op.drop_table("song_categories")


def downgrade() -> None:
    raise NotImplementedError("song library tables are not restored")
