"""data: pre-create + link one auth account per existing member

Calls app.backfill_accounts.backfill_member_accounts on the live
connection. Idempotent (skips already-linked members). Downgrade removes
the auto-created member accounts and unlinks members — identifiable as
role='member' with no discord_id and no password.

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-05
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op
from app.backfill_accounts import backfill_member_accounts

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    backfill_member_accounts(op.get_bind())


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "UPDATE members SET user_id = NULL WHERE user_id IN "
            "(SELECT id FROM users WHERE role = 'member' "
            " AND discord_id IS NULL AND password_hash IS NULL)"
        )
    )
    conn.execute(
        text(
            "DELETE FROM users WHERE role = 'member' "
            "AND discord_id IS NULL AND password_hash IS NULL"
        )
    )
