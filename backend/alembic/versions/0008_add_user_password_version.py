"""add password_version to users

Stamped into the session at login and re-checked on every authenticated
request, so changing a user's password (which bumps this number) evicts
every session that was signed under the old value. Existing rows get
the default of 1 so all previously-issued cookies — which carry no
password_version key — fail the equality check and force a re-login.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "password_version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_version")
