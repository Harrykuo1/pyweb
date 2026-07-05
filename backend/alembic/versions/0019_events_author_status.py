"""events: add author/status/review columns (no anonymity)

Legacy events backfill to status='accepted' via server_default. Author is
null on old rows.

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("events") as batch:
        batch.add_column(sa.Column("author_user_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("last_edited_by_user_id", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "status",
                sa.Enum(
                    "pending",
                    "accepted",
                    "rejected",
                    name="event_status",
                    create_constraint=True,
                ),
                nullable=False,
                server_default="accepted",
            )
        )
        batch.add_column(sa.Column("review_reason", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_foreign_key(
            "fk_events_author_user_id_users", "users", ["author_user_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_events_last_edited_by_user_id_users",
            "users",
            ["last_edited_by_user_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_events_reviewed_by_user_id_users",
            "users",
            ["reviewed_by_user_id"],
            ["id"],
        )
        batch.create_index("ix_events_status", ["status"])


def downgrade() -> None:
    with op.batch_alter_table("events") as batch:
        batch.drop_index("ix_events_status")
        # Drop the enum CHECK before dropping the status column it guards,
        # else the rebuilt table keeps a CHECK on a non-existent column.
        batch.drop_constraint("event_status", type_="check")
        batch.drop_constraint(
            "fk_events_reviewed_by_user_id_users", type_="foreignkey"
        )
        batch.drop_constraint(
            "fk_events_last_edited_by_user_id_users", type_="foreignkey"
        )
        batch.drop_constraint("fk_events_author_user_id_users", type_="foreignkey")
        batch.drop_column("reviewed_at")
        batch.drop_column("reviewed_by_user_id")
        batch.drop_column("review_reason")
        batch.drop_column("status")
        batch.drop_column("last_edited_by_user_id")
        batch.drop_column("author_user_id")
