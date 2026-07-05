"""add events, event_tags and event_photos tables

Backs the community-events feature: each event records a gathering
(dinner, outing, competition, talk, workshop, ...) with free-form tags
and a gallery of photos. Photo binaries live on disk under
data/uploads/events/<event_id>/ for the same reason job attachments and
member photos do — keeping multi-MB blobs out of SQLite. ON DELETE
CASCADE on the child FKs keeps tag/photo rows from orphaning when an
event is removed; the on-disk photo files are cleaned up explicitly by
the delete endpoint.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.Column("description_md", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_events_event_date", "events", ["event_date"])

    op.create_table(
        "event_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_event_tags_event_id", "event_tags", ["event_id"])
    op.create_index("ix_event_tags_name", "event_tags", ["name"])

    op.create_table(
        "event_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("caption", sa.String(length=200), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_event_photos_event_id", "event_photos", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_event_photos_event_id", table_name="event_photos")
    op.drop_table("event_photos")
    op.drop_index("ix_event_tags_name", table_name="event_tags")
    op.drop_index("ix_event_tags_event_id", table_name="event_tags")
    op.drop_table("event_tags")
    op.drop_index("ix_events_event_date", table_name="events")
    op.drop_table("events")
