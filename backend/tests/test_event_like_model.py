from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Event, EventLike, PostStatus, User, UserRole


def _event_and_user(db_session):
    user = User(role=UserRole.MEMBER, discord_id="800")
    db_session.add(user)
    db_session.flush()
    event = Event(
        title="淨灘",
        event_date=date(2024, 6, 1),
        author_user_id=user.id,
        status=PostStatus.ACCEPTED,
    )
    db_session.add(event)
    db_session.flush()
    return event, user


def test_like_persists(db_session):
    event, user = _event_and_user(db_session)
    db_session.add(EventLike(event_id=event.id, user_id=user.id))
    db_session.commit()
    row = db_session.query(EventLike).one()
    assert row.event_id == event.id
    assert row.user_id == user.id
    assert row.created_at is not None


def test_duplicate_like_rejected_by_unique_constraint(db_session):
    event, user = _event_and_user(db_session)
    db_session.add(EventLike(event_id=event.id, user_id=user.id))
    db_session.commit()
    db_session.add(EventLike(event_id=event.id, user_id=user.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_event_cascades_its_likes(db_session):
    event, user = _event_and_user(db_session)
    db_session.add(EventLike(event_id=event.id, user_id=user.id))
    db_session.commit()
    db_session.delete(event)
    db_session.commit()
    assert db_session.query(EventLike).count() == 0
