"""add nullable category column to jobs

Adds a free-text job category (e.g. "Backend", "DevOps", "R&D") that
is orthogonal to the existing kind enum (intern/fulltime). Stored as
nullable since pre-existing rows have no category recorded; users can
backfill via the edit form. An index speeds up the multi-select chip
filter (`?category=A&category=B`) on the list endpoint.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(
            sa.Column("category", sa.String(length=64), nullable=True)
        )
        batch.create_index("ix_jobs_category", ["category"])


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_index("ix_jobs_category")
        batch.drop_column("category")
