"""drop members.photo and members.resume_pdf BLOB columns

Phase 2 of the BLOB-to-filesystem rollout. Revision 0013 added the
path columns and atomically copied every populated BLOB onto disk
(then NULLed the columns). The router has been reading exclusively
from disk since, so the BLOB columns are deadweight now.

SQLite can't ``ALTER TABLE DROP COLUMN`` directly, so ``batch_alter_table``
takes the table-rebuild path under the hood — copy the surviving
columns into a new table and swap it in. Existing rows keep their
photo_path / resume_pdf_path values; nothing on disk moves.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("members") as batch:
        batch.drop_column("resume_pdf")
        batch.drop_column("photo")


def downgrade() -> None:
    # The bytes themselves are gone — downgrade just restores the
    # columns as empty so the schema shape matches 0013. An operator
    # who needs the data back has to recover from a pre-drop backup.
    with op.batch_alter_table("members") as batch:
        batch.add_column(sa.Column("photo", sa.LargeBinary, nullable=True))
        batch.add_column(sa.Column("resume_pdf", sa.LargeBinary, nullable=True))
