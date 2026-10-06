"""First-login migration bridge for existing (pre-created) member accounts.

A Phase-1 backfilled account carries pending_discord_username (the @handle
parsed from the member's resume) and a null discord_id. On that member's
first Discord login we match the live username against it and, on a unique
hit, permanently bind discord_id -- every later login goes by id, so the
handle can change afterwards without breaking anything.

No unique match -> the verified Discord identity is parked in
pending_discord_links for an admin to attach to the right member. We never
auto-link when the match is ambiguous (two candidates), so a re-registered
old handle can't silently bind to the wrong person.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.discord_oauth import DiscordIdentity
from app.models import PendingDiscordLink, User


def normalize_discord_handle(raw: str | None) -> str | None:
    """Clean an admin-entered Discord username for use as a pending link
    target: trim, drop a leading '@', empty -> None. Case is preserved;
    matching against the live username is case-insensitive."""
    if raw is None:
        return None
    cleaned = raw.strip().lstrip("@").strip()
    return cleaned or None


def pending_account_candidates(db: Session, username: str) -> list[User]:
    """Pre-created, not-yet-linked accounts whose pending handle matches
    `username` case-insensitively. A unique hit is safe to bind; more than
    one is ambiguous."""
    return (
        db.query(User)
        .filter(
            User.discord_id.is_(None),
            func.lower(User.pending_discord_username) == username.lower(),
        )
        .order_by(User.id)
        .populate_existing()
        .with_for_update()
        .all()
    )


def clear_pending_link(db: Session, discord_id: str) -> None:
    """Remove any queued pending-link row for this identity once it has been
    bound to an account, so it can't later be re-resolved onto a taken id."""
    db.query(PendingDiscordLink).filter_by(discord_id=discord_id).delete()


def bind_identity(user: User, identity: DiscordIdentity) -> None:
    """Permanently attach a verified Discord identity to a waiting account
    and clear the one-time pending handle. Does not commit."""
    user.discord_id = identity.id
    user.discord_username = identity.username
    user.discord_global_name = identity.global_name
    user.pending_discord_username = None


def queue_pending_link(db: Session, identity: DiscordIdentity) -> None:
    """Park a verified Discord identity in pending_discord_links for an admin
    to attach to the right member. Upserts on discord_id so a repeat login
    refreshes the recorded handle. Does not commit."""
    existing = (
        db.query(PendingDiscordLink).filter_by(discord_id=identity.id).one_or_none()
    )
    if existing is None:
        db.add(
            PendingDiscordLink(
                discord_id=identity.id,
                discord_username=identity.username,
                discord_global_name=identity.global_name,
                first_seen_at=datetime.now(UTC),
            )
        )
    else:
        existing.discord_username = identity.username
        existing.discord_global_name = identity.global_name


def link_or_queue(db: Session, identity: DiscordIdentity) -> User | str | None:
    """Try to bind this Discord identity to a waiting pre-created account.

    Returns the now-linked User (caller logs them in) on a unique handle
    match; returns "suspended" when the sole match is a suspended account
    (nothing is mutated); returns None after queueing a PendingDiscordLink
    otherwise.
    """
    candidates = pending_account_candidates(db, identity.username)

    if len(candidates) == 1:
        user = candidates[0]
        if not user.is_active:
            # Suspended pre-created account: do not bind or queue; the caller
            # turns the login away without mutating anything.
            return "suspended"
        bind_identity(user, identity)
        clear_pending_link(db, identity.id)
        db.commit()
        db.refresh(user)
        return user

    # Zero or ambiguous match -> queue for manual admin linking.
    queue_pending_link(db, identity)
    db.commit()
    return None
