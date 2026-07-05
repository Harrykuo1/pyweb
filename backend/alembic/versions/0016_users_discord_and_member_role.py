"""users: add discord fields, relax username/password_hash, add MEMBER role

Foundation for Discord OAuth. discord_id is the permanent identity key
(unique, nullable until first login). username/password_hash become
nullable because Discord accounts have neither. The user_role CHECK is
widened to include 'member'.

SQLite can't ALTER in place, so batch mode rebuilds the table. Batch
reflection carries the existing named enum CHECK ("user_role", allowing
only admin/viewer) over to the rebuilt table verbatim, so widening the
enum means explicitly dropping that CHECK and emitting a new one — an
alter_column type change alone leaves the old CHECK in place.

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("discord_id", sa.String(length=32), nullable=True))
        batch.add_column(
            sa.Column("discord_username", sa.String(length=64), nullable=True)
        )
        batch.add_column(
            sa.Column("discord_global_name", sa.String(length=128), nullable=True)
        )
        batch.add_column(
            sa.Column("pending_discord_username", sa.String(length=64), nullable=True)
        )
        batch.alter_column(
            "username", existing_type=sa.String(length=64), nullable=True
        )
        batch.alter_column(
            "password_hash", existing_type=sa.String(length=255), nullable=True
        )
        batch.drop_constraint("user_role", type_="check")
        batch.create_check_constraint(
            "user_role", "role IN ('admin', 'viewer', 'member')"
        )
    op.create_index("ix_users_discord_id", "users", ["discord_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_discord_id", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("user_role", type_="check")
        batch.create_check_constraint("user_role", "role IN ('admin', 'viewer')")
        batch.alter_column(
            "password_hash", existing_type=sa.String(length=255), nullable=False
        )
        batch.alter_column(
            "username", existing_type=sa.String(length=64), nullable=False
        )
        batch.drop_column("pending_discord_username")
        batch.drop_column("discord_global_name")
        batch.drop_column("discord_username")
        batch.drop_column("discord_id")
