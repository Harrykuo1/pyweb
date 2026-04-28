"""baseline schema (pre-Alembic state)

Captures the schema as it existed before Alembic was introduced:
users, members, site_settings, and internships *without* the kind
column. New deployments run this migration to create everything.
Existing deployments — where these tables already exist — should run
`alembic stamp 0001` instead, then `alembic upgrade head` to apply
later migrations.

Revision ID: 0001
Revises:
Create Date: 2026-04-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "viewer", name="user_role", create_constraint=True),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("graduation_year", sa.Integer(), nullable=False),
        sa.Column("real_name", sa.String(length=64), nullable=False),
        sa.Column("current_position", sa.String(length=255), nullable=False),
        sa.Column("photo", sa.LargeBinary(), nullable=True),
        sa.Column("photo_content_type", sa.String(length=50), nullable=True),
        sa.Column("resume_md", sa.Text(), nullable=True),
        sa.Column("resume_pdf", sa.LargeBinary(), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "site_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.LargeBinary(), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "internships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_year", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(length=128), nullable=False),
        sa.Column("experience_md", sa.Text(), nullable=False),
        sa.Column("real_name", sa.String(length=64), nullable=True),
        sa.Column("timeline_md", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("internships")
    op.drop_table("site_settings")
    op.drop_table("members")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
