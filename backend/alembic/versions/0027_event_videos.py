"""add event_videos (uploaded + YouTube), with a shape CHECK

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_videos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "upload", "youtube", name="event_video_kind", create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "processing",
                "ready",
                "failed",
                name="event_video_status",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("caption", sa.String(length=200), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        # kind=upload only. Null while transcoding and after a failure.
        sa.Column("filename", sa.String(length=256), nullable=True),
        sa.Column("poster_filename", sa.String(length=256), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        # kind=youtube only: the 11-char id, never the pasted URL.
        sa.Column("youtube_id", sa.String(length=11), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        # One row holds either an uploaded file or a YouTube reference. The
        # users table keeps the same shape without a constraint, and the rule
        # that a Discord account has no password survived only in a comment
        # until it drifted. This one lives in the schema.
        sa.CheckConstraint(
            "(kind = 'youtube' AND filename IS NULL"
            " AND youtube_id IS NOT NULL AND length(youtube_id) = 11)"
            " OR (kind = 'upload' AND youtube_id IS NULL)",
            name="ck_event_videos_kind_shape",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("event_videos", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_event_videos_event_id"), ["event_id"], unique=False
        )
        # The startup sweep scans for rows stuck in PROCESSING.
        batch_op.create_index(
            batch_op.f("ix_event_videos_status"), ["status"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("event_videos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_event_videos_status"))
        batch_op.drop_index(batch_op.f("ix_event_videos_event_id"))

    op.drop_table("event_videos")
