"""worship_sessions — presentation_filename · library_category."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_worship_session_library_target"
down_revision: Union[str, Sequence[str], None] = "004_venue_runtime_worship_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "worship_sessions",
        sa.Column("presentation_filename", sa.Text(), nullable=True),
    )
    op.add_column(
        "worship_sessions",
        sa.Column("library_category", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("worship_sessions", "library_category")
    op.drop_column("worship_sessions", "presentation_filename")
