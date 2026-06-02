"""initial song library schema"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_song_library"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.create_table(
        "songs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("title_normalized", sa.Text(), nullable=False),
        sa.Column("artist", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_songs_title_normalized",
        "songs",
        ["title_normalized"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "song_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("song_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("lines", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_song_sections_song_id", "song_sections", ["song_id", "sort_order"])
    op.create_table(
        "song_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("song_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_job_id", sa.Text(), nullable=True),
        sa.Column("input_kind", sa.Text(), nullable=True),
        sa.Column("client_ref", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_song_sources_job_id",
        "song_sources",
        ["source_job_id"],
        unique=False,
        postgresql_where=sa.text("source_job_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_song_sources_job_id", table_name="song_sources")
    op.drop_table("song_sources")
    op.drop_index("idx_song_sections_song_id", table_name="song_sections")
    op.drop_table("song_sections")
    op.drop_index("idx_songs_title_normalized", table_name="songs")
    op.drop_table("songs")
