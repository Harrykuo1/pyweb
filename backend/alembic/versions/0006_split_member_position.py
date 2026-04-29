"""split members.current_position into institution + position

The single freeform `current_position` field captured both the
school/company name and the department/role in one string. Splitting
into a required `institution` (學校／公司) and optional `position`
(系所／職位) lets the UI render the two on separate lines and lets
admins fill them in independently.

For existing rows the entire prior `current_position` value is copied
verbatim into `institution`, with `position` left NULL — admins are
expected to manually move the role portion out via the edit form
because the freeform values were too inconsistent to auto-split safely.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the two new columns as nullable first so SQLite is happy with
    # the existing rows during the table rebuild.
    with op.batch_alter_table("members") as batch:
        batch.add_column(sa.Column("institution", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("position", sa.String(length=128), nullable=True))

    # Copy the entire old value into institution; position stays NULL.
    op.execute(
        "UPDATE members SET institution = current_position WHERE institution IS NULL"
    )

    # Now that every row has a value, lock institution to NOT NULL and
    # drop the legacy column.
    with op.batch_alter_table("members") as batch:
        batch.alter_column(
            "institution",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch.drop_column("current_position")


def downgrade() -> None:
    # Re-add current_position, fold institution + position back into one
    # string (separated by a space when both are present), then drop the
    # split columns. Lossy by design — no way to recover the original
    # exact whitespace, but admins editing again will fix it.
    with op.batch_alter_table("members") as batch:
        batch.add_column(sa.Column("current_position", sa.String(length=255), nullable=True))

    op.execute(
        "UPDATE members SET current_position = TRIM(institution || ' ' || COALESCE(position, ''))"
    )

    with op.batch_alter_table("members") as batch:
        batch.alter_column(
            "current_position",
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch.drop_column("position")
        batch.drop_column("institution")
