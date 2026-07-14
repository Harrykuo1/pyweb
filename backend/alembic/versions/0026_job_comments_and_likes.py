"""add job_comments and job_likes tables (mirror the event ones)

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_job_comments_job_id", "job_comments", ["job_id"])

    op.create_table(
        "job_likes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "user_id", name="uq_job_likes_job_user"),
    )
    op.create_index("ix_job_likes_job_id", "job_likes", ["job_id"])
    op.create_index("ix_job_likes_user_id", "job_likes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_job_likes_user_id", table_name="job_likes")
    op.drop_index("ix_job_likes_job_id", table_name="job_likes")
    op.drop_table("job_likes")
    op.drop_index("ix_job_comments_job_id", table_name="job_comments")
    op.drop_table("job_comments")
