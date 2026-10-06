"""Record completed database initialization/import atomically with its data."""

import sqlalchemy as sa

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "database_origin",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("identity", sa.String(32), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tables", sa.JSON(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_database_origin_singleton"),
    )


def downgrade():
    op.drop_table("database_origin")
