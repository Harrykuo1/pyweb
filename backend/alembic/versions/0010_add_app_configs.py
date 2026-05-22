"""add app_configs scalar key/value table

Stores admin-tunable runtime config (e.g. attachment count limit,
file size limit) separately from site_settings, which is reserved
for binary assets like the login logo. The schema is intentionally
generic — value is stored as text and parsed against a typed
schema (app.core.runtime_config) at the API layer, so adding new
config knobs in the future is a row-level operation, not a schema
migration.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_configs",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.String(length=512), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_configs")
