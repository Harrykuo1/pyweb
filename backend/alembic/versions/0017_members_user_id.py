"""members: add user_id FK linking a member profile to its auth account

1:1 link (unique, nullable). Nullable so the migration can add the column
before backfilling; the data migration (0022) pre-creates one user per
member and fills this in.

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("members") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_members_user_id_users", "users", ["user_id"], ["id"]
        )
    op.create_index("ix_members_user_id", "members", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_members_user_id", table_name="members")
    with op.batch_alter_table("members") as batch:
        batch.drop_constraint("fk_members_user_id_users", type_="foreignkey")
        batch.drop_column("user_id")
