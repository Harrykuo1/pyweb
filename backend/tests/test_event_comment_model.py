from datetime import date

from app.models import Event, EventComment, PostStatus, User, UserRole


def _event_with_author(db_session):
    author = User(role=UserRole.MEMBER, discord_id="700")
    db_session.add(author)
    db_session.flush()
    event = Event(
        title="桌遊夜",
        event_date=date(2024, 5, 1),
        author_user_id=author.id,
        status=PostStatus.ACCEPTED,
    )
    db_session.add(event)
    db_session.flush()
    return event, author


def test_comment_persists_with_author(db_session):
    event, author = _event_with_author(db_session)
    db_session.add(
        EventComment(event_id=event.id, author_user_id=author.id, body="好好玩")
    )
    db_session.commit()

    fetched = db_session.query(EventComment).one()
    assert fetched.body == "好好玩"
    assert fetched.author_user_id == author.id
    assert fetched.created_at is not None
    assert fetched.edited_at is None


def test_deleting_event_cascades_its_comments(db_session):
    event, author = _event_with_author(db_session)
    db_session.add_all(
        [
            EventComment(event_id=event.id, author_user_id=author.id, body="一"),
            EventComment(event_id=event.id, author_user_id=author.id, body="二"),
        ]
    )
    db_session.commit()

    db_session.delete(event)
    db_session.commit()

    assert db_session.query(EventComment).count() == 0
