"""add required job_month column to jobs

Adds a 1-12 month component alongside job_year so records can capture
the exact month a position search happened, not just the year. The
column is non-null with a server-side default of 1 so existing rows
(if any) stay valid at migration time; the application always supplies
a real month on insert.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(
            sa.Column(
                "job_month",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("job_month")
