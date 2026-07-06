from datetime import UTC, datetime, timedelta

from app.core.discord_register import invite_is_valid
from app.models import RegistrationInvite


def _invite(**kw):
    now = datetime.now(UTC)
    defaults = dict(token="t", created_at=now, expires_at=now + timedelta(hours=1))
    defaults.update(kw)
    return RegistrationInvite(**defaults)


def test_invite_valid_when_fresh_and_unused():
    now = datetime.now(UTC)
    assert invite_is_valid(_invite(), now) is True


def test_invite_invalid_when_none():
    assert invite_is_valid(None, datetime.now(UTC)) is False


def test_invite_invalid_when_used():
    now = datetime.now(UTC)
    assert invite_is_valid(_invite(used_at=now), now) is False


def test_invite_invalid_when_expired():
    now = datetime.now(UTC)
    expired = _invite(expires_at=now - timedelta(minutes=1))
    assert invite_is_valid(expired, now) is False


def test_invite_valid_handles_naive_expires_at():
    # SQLite can hand back a tz-naive datetime; validity must not blow up.
    now = datetime.now(UTC)
    naive = _invite(expires_at=(now + timedelta(hours=1)).replace(tzinfo=None))
    assert invite_is_valid(naive, now) is True
