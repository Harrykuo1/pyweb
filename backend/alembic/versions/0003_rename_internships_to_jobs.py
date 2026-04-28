"""rename internships table to jobs

A pure table-name rename. The column shape, indexes and JobKind enum
constraint stay identical — only the table identifier changes so it
matches the application-layer rename of the ORM model from Internship
to Job.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("internships", "jobs")


def downgrade() -> None:
    op.rename_table("jobs", "internships")
