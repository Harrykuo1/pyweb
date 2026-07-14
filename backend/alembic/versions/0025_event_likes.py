"""add event_likes table (one heart per member per event)

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_likes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_likes_event_user"),
    )
    op.create_index("ix_event_likes_event_id", "event_likes", ["event_id"])
    op.create_index("ix_event_likes_user_id", "event_likes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_event_likes_user_id", table_name="event_likes")
    op.drop_index("ix_event_likes_event_id", table_name="event_likes")
    op.drop_table("event_likes")
