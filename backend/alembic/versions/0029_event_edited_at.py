"""Record the latest event edit for the community timeline.

Revision ID: 0029
Revises: 0028
"""

import sqlalchemy as sa

from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical edit times were never stored; leave them unknown.
    with op.batch_alter_table("events") as batch:
        batch.add_column(
            sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_index("ix_events_edited_at", ["edited_at"])


def downgrade() -> None:
    with op.batch_alter_table("events") as batch:
        batch.drop_index("ix_events_edited_at")
        batch.drop_column("edited_at")
