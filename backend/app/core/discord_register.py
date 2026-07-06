"""New-member registration via a one-time invite link.

Discord allows a single redirect URI, so registration reuses the login
callback and is distinguished by a registration_invite_token stashed in
the session. Kept as small pure-ish functions so validity and account
creation are unit-testable without HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models import RegistrationInvite


def invite_is_valid(invite: RegistrationInvite | None, now: datetime) -> bool:
    if invite is None or invite.used_at is not None:
        return False
    expires = invite.expires_at
    if expires.tzinfo is None:
        # SQLite may hand back a tz-naive value; treat stored time as UTC.
        expires = expires.replace(tzinfo=UTC)
    return now < expires
