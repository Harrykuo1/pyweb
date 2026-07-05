from datetime import date

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models import Event, PostStatus, User, UserRole


def test_event_new_columns(db_session):
    author = User(role=UserRole.MEMBER, discord_id="600")
    db_session.add(author)
    db_session.flush()

    event = Event(
        title="春酒",
        event_date=date(2024, 1, 20),
        author_user_id=author.id,
        status=PostStatus.PENDING,
    )
    db_session.add(event)
    db_session.commit()

    fetched = db_session.query(Event).one()
    assert fetched.status is PostStatus.PENDING
    assert fetched.author_user_id == author.id
    assert fetched.reviewed_at is None


def test_event_status_rejects_invalid(db_session):
    event = Event(title="X", event_date=date(2024, 1, 1), status="live")
    db_session.add(event)
    with pytest.raises(SQLAlchemyError):
        db_session.commit()
    db_session.rollback()
