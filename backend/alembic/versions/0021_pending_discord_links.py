"""add pending_discord_links table (unmatched first-login queue)

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_discord_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("discord_id", sa.String(length=32), nullable=False),
        sa.Column("discord_username", sa.String(length=64), nullable=True),
        sa.Column("discord_global_name", sa.String(length=128), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_pending_discord_links_discord_id",
        "pending_discord_links",
        ["discord_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pending_discord_links_discord_id", table_name="pending_discord_links"
    )
    op.drop_table("pending_discord_links")
