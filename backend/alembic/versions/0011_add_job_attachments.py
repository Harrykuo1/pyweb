"""add job_attachments table for job-record file uploads

Backs the new attachment feature on jobs: each row holds metadata for
one file uploaded against a job (PDF, PPT, Word, image, etc.). The
binary itself lives on the filesystem under data/uploads/<job_id>/
because storing 20MB BLOBs inside SQLite would balloon the DB and
slow every other query that touches the page cache. ON DELETE CASCADE
on job_id keeps orphan-row cleanup automatic when a job is deleted;
the on-disk files are cleaned up explicitly by the delete endpoint.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_job_attachments_job_id",
        "job_attachments",
        ["job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_attachments_job_id", table_name="job_attachments")
    op.drop_table("job_attachments")
