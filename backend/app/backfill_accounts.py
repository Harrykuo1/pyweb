"""One-time backfill: pre-create an auth account per existing member.

Called by Alembic migration 0022. Kept dependency-light (SQLAlchemy Core,
no ORM models) so it stays valid even if the models drift later. Parses
the Discord @handle out of each member's resume markdown — the format is
uniformly ``- Discord: `handle` `` in the seeded data — and stores it as
pending_discord_username for the first-login bridge. Members with no
parseable handle still get an account (handle left null) so an admin can
link them manually.

Idempotent: members that already have user_id are skipped.
"""

import re
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

_HANDLE_RE = re.compile(r"Discord:\s*`([^`]+)`", re.IGNORECASE)


def _parse_handle(resume_md: str | None) -> str | None:
    if not resume_md:
        return None
    m = _HANDLE_RE.search(resume_md)
    return m.group(1).strip() if m else None


def backfill_member_accounts(connection: Connection) -> int:
    """Create + link one member account per unlinked member. Returns the
    number of accounts created."""
    now = datetime.now(UTC)
    rows = connection.execute(
        text("SELECT id, resume_md FROM members WHERE user_id IS NULL")
    ).all()

    created = 0
    for member_id, resume_md in rows:
        handle = _parse_handle(resume_md)
        result = connection.execute(
            text(
                "INSERT INTO users "
                "(username, password_hash, password_version, discord_id, "
                " discord_username, discord_global_name, "
                " pending_discord_username, role, created_at) "
                "VALUES "
                "(NULL, NULL, 1, NULL, NULL, NULL, :handle, 'member', :now) RETURNING id"
            ),
            {"handle": handle, "now": now},
        )
        user_id = result.scalar_one()
        connection.execute(
            text("UPDATE members SET user_id = :uid WHERE id = :mid"),
            {"uid": user_id, "mid": member_id},
        )
        created += 1
    return created
