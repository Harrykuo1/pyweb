from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import RegistrationInvite


def test_create_invite(db_session):
    now = datetime.now(UTC)
    inv = RegistrationInvite(
        token="abc123",
        created_at=now,
        expires_at=now + timedelta(hours=48),
    )
    db_session.add(inv)
    db_session.commit()

    fetched = db_session.query(RegistrationInvite).one()
    assert fetched.token == "abc123"
    assert fetched.used_at is None
    assert fetched.used_by_user_id is None


def test_invite_token_is_unique(db_session):
    now = datetime.now(UTC)
    db_session.add(RegistrationInvite(token="dup", created_at=now, expires_at=now))
    db_session.commit()
    db_session.add(RegistrationInvite(token="dup", created_at=now, expires_at=now))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
