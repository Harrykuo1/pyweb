"""New-member registration via a one-time invite link.

Discord allows a single redirect URI, so registration reuses the login
callback and is distinguished by a registration_invite_token stashed in
the session. Kept as small pure-ish functions so validity and account
creation are unit-testable without HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.discord_link import bind_identity, pending_account_candidates
from app.core.discord_oauth import DiscordIdentity
from app.models import RegistrationInvite, User, UserRole


def invite_is_valid(invite: RegistrationInvite | None, now: datetime) -> bool:
    if invite is None or invite.used_at is not None:
        return False
    expires = invite.expires_at
    if expires.tzinfo is None:
        # SQLite may hand back a tz-naive value; treat stored time as UTC.
        expires = expires.replace(tzinfo=UTC)
    return now < expires


def register_via_invite(
    db: Session, identity: DiscordIdentity, token: str
) -> tuple[User | None, str | None]:
    """Create a new member account bound to `identity`, consuming the
    invite. Returns (user, None) on success or (None, error_reason)."""
    now = datetime.now(UTC)
    invite = db.query(RegistrationInvite).filter_by(token=token).one_or_none()
    if not invite_is_valid(invite, now):
        return None, "invalid_invite"

    already = db.query(User).filter_by(discord_id=identity.id).one_or_none()
    if already is not None:
        return None, "already_registered"

    # If an admin already pre-created this member (a unique pending-handle
    # match), claim that existing account instead of minting a duplicate.
    # Guards against two member records for one person when both an invite
    # and a pre-provisioned account exist.
    candidates = pending_account_candidates(db, identity.username)
    if len(candidates) == 1:
        user = candidates[0]
        bind_identity(user, identity)
        invite.used_at = now
        invite.used_by_user_id = user.id
        db.commit()
        db.refresh(user)
        return user, None

    user = User(
        role=UserRole.MEMBER,
        discord_id=identity.id,
        discord_username=identity.username,
        discord_global_name=identity.global_name,
    )
    db.add(user)
    db.flush()
    invite.used_at = now
    invite.used_by_user_id = user.id
    db.commit()
    db.refresh(user)
    return user, None
