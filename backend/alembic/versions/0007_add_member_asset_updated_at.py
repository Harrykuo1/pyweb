"""add photo_updated_at and resume_pdf_updated_at to members

Tracks the last time the binary asset (photo / resume PDF) was uploaded
so the frontend can use it as a cache-busting URL version stamp instead
of forcing a re-download on every dialog open.

For existing rows that already have a photo / PDF, we backfill the
timestamp from `joined_at` — it's the best approximation we have for
"when did this asset get into the system" and it gives every legacy
asset a stable, non-NULL version that won't change spuriously. Rows
without the asset stay NULL.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("members") as batch:
        batch.add_column(
            sa.Column("photo_updated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "resume_pdf_updated_at", sa.DateTime(timezone=True), nullable=True
            )
        )

    op.execute(
        "UPDATE members SET photo_updated_at = joined_at WHERE photo IS NOT NULL"
    )
    op.execute(
        "UPDATE members SET resume_pdf_updated_at = joined_at WHERE resume_pdf IS NOT NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("members") as batch:
        batch.drop_column("resume_pdf_updated_at")
        batch.drop_column("photo_updated_at")
