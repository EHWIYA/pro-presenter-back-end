"""venue_runtime · worship_sessions 테이블."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_venue_runtime_worship_sessions"
down_revision: Union[str, Sequence[str], None] = "003_song_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "venue_runtime",
        sa.Column("venue_id", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("pp_reachable", sa.Boolean(), nullable=True),
        sa.Column("pp_current_presentation_id", sa.Text(), nullable=True),
        sa.Column("pp_current_slide_index", sa.Integer(), nullable=True),
        sa.Column("pp_preview_text", sa.Text(), nullable=True),
        sa.Column("agent_reachable", sa.Boolean(), nullable=True),
        sa.Column("agent_version", sa.Text(), nullable=True),
        sa.Column("agent_last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_git_revision", sa.Text(), nullable=True),
        sa.Column("data_reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_build_session_id", sa.Uuid(), nullable=True),
        sa.Column("last_build_kind", sa.Text(), nullable=True),
        sa.Column("last_build_reference", sa.Text(), nullable=True),
        sa.Column("last_build_slide_map", json_type, nullable=True),
        sa.Column("last_build_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("venue_id"),
    )
    op.create_table(
        "worship_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), server_default="scripture", nullable=False),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("slide_map", json_type, server_default="[]", nullable=False),
        sa.Column("slide_count", sa.Integer(), nullable=True),
        sa.Column("total_slide_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_triggered_index", sa.Integer(), nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_worship_sessions_venue_id", "worship_sessions", ["venue_id"])


def downgrade() -> None:
    op.drop_index("idx_worship_sessions_venue_id", table_name="worship_sessions")
    op.drop_table("worship_sessions")
    op.drop_table("venue_runtime")
