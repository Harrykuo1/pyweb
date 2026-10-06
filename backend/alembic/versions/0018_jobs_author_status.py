"""jobs: add author/subject/anonymity/status/review columns

Legacy rows are backfilled to status='accepted' (via server_default) and
is_anonymous is derived from the existing null-real_name anonymity
convention. New author/subject linkage stays null on old rows; admins can
attach a subject later through the edit form.

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("subject_member_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("author_user_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("last_edited_by_user_id", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "is_anonymous",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(
            sa.Column(
                "status",
                sa.Enum(
                    "pending",
                    "accepted",
                    "rejected",
                    name="job_status",
                    native_enum=False,
                    create_constraint=True,
                ),
                nullable=False,
                server_default="accepted",
            )
        )
        batch.add_column(sa.Column("review_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_foreign_key(
            "fk_jobs_subject_member_id_members",
            "members",
            ["subject_member_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_jobs_author_user_id_users", "users", ["author_user_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_jobs_last_edited_by_user_id_users",
            "users",
            ["last_edited_by_user_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_jobs_reviewed_by_user_id_users",
            "users",
            ["reviewed_by_user_id"],
            ["id"],
        )
        batch.create_index("ix_jobs_subject_member_id", ["subject_member_id"])
        batch.create_index("ix_jobs_status", ["status"])
    # Preserve the existing anonymity convention: rows with no real_name
    # were the anonymous ones.
    op.execute("UPDATE jobs SET is_anonymous = true WHERE real_name IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_index("ix_jobs_status")
        batch.drop_index("ix_jobs_subject_member_id")
        # The reflected enum CHECK references the status column we're about
        # to drop; remove it explicitly or the rebuilt table keeps a CHECK
        # on a non-existent column.
        batch.drop_constraint("job_status", type_="check")
        batch.drop_constraint("fk_jobs_reviewed_by_user_id_users", type_="foreignkey")
        batch.drop_constraint(
            "fk_jobs_last_edited_by_user_id_users", type_="foreignkey"
        )
        batch.drop_constraint("fk_jobs_author_user_id_users", type_="foreignkey")
        batch.drop_constraint("fk_jobs_subject_member_id_members", type_="foreignkey")
        batch.drop_column("reviewed_at")
        batch.drop_column("reviewed_by_user_id")
        batch.drop_column("review_reason")
        batch.drop_column("status")
        batch.drop_column("is_anonymous")
        batch.drop_column("last_edited_by_user_id")
        batch.drop_column("author_user_id")
        batch.drop_column("subject_member_id")
