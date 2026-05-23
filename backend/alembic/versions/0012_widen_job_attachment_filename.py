"""widen job_attachments.filename to fit relative paths

Folder uploads keep their on-disk hierarchy
(``src/components/Foo.vue``), which can blow past the original 255-
char column easily. Bump to 1024 — long enough for any sane upload
without going TEXT, which on SQLite would just be a label since the
type-affinity rules treat them the same anyway.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("job_attachments") as batch:
        batch.alter_column(
            "filename",
            existing_type=sa.String(length=255),
            type_=sa.String(length=1024),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("job_attachments") as batch:
        batch.alter_column(
            "filename",
            existing_type=sa.String(length=1024),
            type_=sa.String(length=255),
            existing_nullable=False,
        )
