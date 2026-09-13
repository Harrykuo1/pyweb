from datetime import date

import pytest

from app.models import (
    Event,
    EventPhoto,
    EventVideo,
    PostStatus,
    User,
    UserRole,
    VideoKind,
    VideoStatus,
)
from app.routers.events import _photo_aggregates


@pytest.fixture
def event(db_session):
    user = User(role=UserRole.MEMBER, discord_id="910")
    db_session.add(user)
    db_session.flush()
    ev = Event(
        id=1,
        title="排序測試",
        event_date=date(2026, 4, 1),
        author_user_id=user.id,
        status=PostStatus.ACCEPTED,
    )
    db_session.add(ev)
    db_session.flush()
    return ev


def _photo(event_id, n, order):
    return EventPhoto(
        event_id=event_id,
        filename=f"{n}.jpg",
        mime_type="image/jpeg",
        size_bytes=1,
        sort_order=order,
    )


def _video(event_id, order):
    return EventVideo(
        event_id=event_id,
        kind=VideoKind.UPLOAD,
        status=VideoStatus.READY,
        sort_order=order,
    )


def test_photos_and_videos_share_one_sequence(db_session, event):
    """Ordering only means something across both tables — the two render as
    one grid, so a position scoped to photos alone could not interleave."""
    db_session.add_all(
        [
            _photo(event.id, 1, order=30),
            _video(event.id, order=20),
            _photo(event.id, 2, order=10),
        ]
    )
    db_session.commit()

    photos = {p.id: p.sort_order for p in event.photos}
    videos = {v.id: v.sort_order for v in event.videos}
    merged = sorted(
        [("photo", i, o) for i, o in photos.items()]
        + [("video", i, o) for i, o in videos.items()],
        key=lambda r: (r[2], r[0], r[1]),
    )
    # A video sits between two photos, which is the whole point.
    assert [kind for kind, _, _ in merged] == ["photo", "video", "photo"]


def test_relationships_order_by_sort_order_not_id(db_session, event):
    # Inserted so that id order and sort order disagree; the relationship has
    # to follow sort_order or the grid would ignore a reorder entirely.
    first = _photo(event.id, 1, order=90)
    second = _photo(event.id, 2, order=10)
    db_session.add_all([first, second])
    db_session.commit()
    db_session.refresh(event)

    assert [p.sort_order for p in event.photos] == [10, 90]
    assert event.photos[0].id == second.id


def test_sort_order_defaults_so_an_insert_never_fails(db_session, event):
    # Anything creating media without a position still has to work; it lands
    # at the front and a reorder moves it.
    db_session.add(
        EventPhoto(
            event_id=event.id, filename="x.jpg", mime_type="image/jpeg", size_bytes=1
        )
    )
    db_session.commit()
    assert db_session.query(EventPhoto).one().sort_order == 0


def test_the_cover_follows_the_arranged_order_not_the_lowest_id(db_session, event):
    """The cover used to be min(id), which ignored any reordering — dragging
    a photo to the front changed the grid and left the card unchanged."""
    first_uploaded = _photo(event.id, 1, order=90)
    dragged_to_front = _photo(event.id, 2, order=10)
    db_session.add_all([first_uploaded, dragged_to_front])
    db_session.commit()

    count, cover = _photo_aggregates(db_session, [event.id])[event.id]
    assert count == 2
    assert cover == dragged_to_front.id
    assert dragged_to_front.id > first_uploaded.id  # so id order disagrees


def test_cover_falls_back_to_id_when_orders_tie(db_session, event):
    # Media that predates any reordering all sits at 0, so the tiebreaker has
    # to keep the old behaviour rather than picking arbitrarily.
    a = _photo(event.id, 1, order=0)
    b = _photo(event.id, 2, order=0)
    db_session.add_all([a, b])
    db_session.commit()

    _, cover = _photo_aggregates(db_session, [event.id])[event.id]
    assert cover == min(a.id, b.id)
