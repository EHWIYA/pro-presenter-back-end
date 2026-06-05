"""songs.category 컬럼"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_song_category"
down_revision: Union[str, Sequence[str], None] = "001_song_library"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "songs",
        sa.Column("category", sa.Text(), server_default="praise", nullable=False),
    )
    op.create_index(
        "idx_songs_category",
        "songs",
        ["category"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_songs_category", table_name="songs")
    op.drop_column("songs", "category")
