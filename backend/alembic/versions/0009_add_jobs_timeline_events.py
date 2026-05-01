"""add timeline_events JSON column to jobs

The free-form timeline_md markdown column made the recruitment timeline
hard to render consistently and forced the admin to hand-compute D+N
offsets. The replacement is structured per-row data: each entry stores
just month + day + event text, with the year inferred from
job.job_year so leap-year arithmetic stays honest.

The column is nullable and additive: existing rows keep their
timeline_md, and the viewer falls back to rendering the legacy
markdown with a deprecated badge until the admin re-enters the
timeline through the new structured editor.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("timeline_events", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("timeline_events")
