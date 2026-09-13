"""add sort_order to event photos and videos

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # One sequence spanning both tables: photos and videos render as a single
    # grid, so a position only means anything across both. Splitting the
    # column rather than merging the tables keeps the existing photo API and
    # its files untouched; the reorder endpoint renumbers the whole event in
    # one transaction, which is what actually keeps the two consistent.
    for table in ("event_photos", "event_videos"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "sort_order",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
            batch_op.create_index(
                batch_op.f(f"ix_{table}_sort_order"), ["sort_order"], unique=False
            )

    # Backfill from id so every existing event keeps exactly the order it
    # already displayed. Photos came first in the merged grid and videos
    # after, so videos start above any photo id in the same event.
    op.execute(
        """
        UPDATE event_photos
           SET sort_order = id
        """
    )
    op.execute(
        """
        UPDATE event_videos
           SET sort_order = (
                   SELECT COALESCE(MAX(p.id), 0)
                     FROM event_photos p
                    WHERE p.event_id = event_videos.event_id
               ) + event_videos.id
        """
    )


def downgrade() -> None:
    for table in ("event_videos", "event_photos"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(f"ix_{table}_sort_order"))
            batch_op.drop_column("sort_order")
