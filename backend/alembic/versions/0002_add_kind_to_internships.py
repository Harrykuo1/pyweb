"""add kind column to internships

Adds the JobKind discriminator (internship | fulltime) to the
internships table so a single table covers both record kinds. Existing
rows are backfilled with 'internship' via server_default; new rows
must supply kind explicitly through the application layer (Pydantic
Literal validator), but the SQL-level default stays in place as a
safety net for any direct DB inserts.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_JOB_KIND = sa.Enum(
    "internship",
    "fulltime",
    name="job_kind",
    create_constraint=True,
    validate_strings=True,
)


def upgrade() -> None:
    with op.batch_alter_table("internships") as batch:
        batch.add_column(
            sa.Column(
                "kind",
                _JOB_KIND,
                nullable=False,
                server_default="internship",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("internships") as batch:
        batch.drop_column("kind")
