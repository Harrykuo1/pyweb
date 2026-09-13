from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Event,
    EventVideo,
    PostStatus,
    User,
    UserRole,
    VideoKind,
    VideoStatus,
)


def _event(db_session) -> Event:
    user = User(role=UserRole.MEMBER, discord_id="801")
    db_session.add(user)
    db_session.flush()
    event = Event(
        title="尾牙",
        event_date=date(2026, 1, 10),
        author_user_id=user.id,
        status=PostStatus.ACCEPTED,
    )
    db_session.add(event)
    db_session.flush()
    return event


def test_uploaded_video_persists(db_session):
    event = _event(db_session)
    db_session.add(
        EventVideo(
            event_id=event.id,
            kind=VideoKind.UPLOAD,
            status=VideoStatus.PROCESSING,
        )
    )
    db_session.commit()

    row = db_session.query(EventVideo).one()
    assert row.kind is VideoKind.UPLOAD
    assert row.status is VideoStatus.PROCESSING
    # Nothing to serve until transcoding finishes.
    assert row.filename is None
    assert row.youtube_id is None


def test_youtube_video_persists(db_session):
    event = _event(db_session)
    db_session.add(
        EventVideo(
            event_id=event.id,
            kind=VideoKind.YOUTUBE,
            status=VideoStatus.READY,
            youtube_id="dQw4w9WgXcQ",
        )
    )
    db_session.commit()

    row = db_session.query(EventVideo).one()
    assert row.youtube_id == "dQw4w9WgXcQ"
    assert row.filename is None


# The users table holds two identities in one row with no constraint, and the
# rule that a Discord account never has a password lived only in a comment
# until it drifted. These pin the equivalent rule here into the schema.
@pytest.mark.parametrize(
    "label,kwargs",
    [
        (
            "youtube without an id",
            {"kind": VideoKind.YOUTUBE, "youtube_id": None},
        ),
        (
            "youtube id that is not 11 chars",
            {"kind": VideoKind.YOUTUBE, "youtube_id": "abc"},
        ),
        (
            "youtube carrying a filename",
            {
                "kind": VideoKind.YOUTUBE,
                "youtube_id": "dQw4w9WgXcQ",
                "filename": "1.mp4",
            },
        ),
        (
            "upload carrying a youtube id",
            {"kind": VideoKind.UPLOAD, "youtube_id": "dQw4w9WgXcQ"},
        ),
    ],
)
def test_kind_shape_is_enforced_by_the_database(db_session, label, kwargs):
    event = _event(db_session)
    db_session.add(EventVideo(event_id=event.id, status=VideoStatus.READY, **kwargs))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_the_event_takes_its_videos(db_session):
    event = _event(db_session)
    db_session.add(
        EventVideo(
            event_id=event.id,
            kind=VideoKind.YOUTUBE,
            status=VideoStatus.READY,
            youtube_id="dQw4w9WgXcQ",
        )
    )
    db_session.commit()

    db_session.delete(event)
    db_session.commit()
    assert db_session.query(EventVideo).count() == 0
