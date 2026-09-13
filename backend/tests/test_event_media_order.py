from datetime import date

import pytest

from app.core.event_media import next_sort_order
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
from app.routers.events import _media_summaries


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
    # A READY upload always carries both files — the transcode writes them
    # together and flips the status last.
    return EventVideo(
        event_id=event_id,
        kind=VideoKind.UPLOAD,
        status=VideoStatus.READY,
        sort_order=order,
        filename="1.mp4",
        poster_filename="1.jpg",
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

    summary = _media_summaries(db_session, [event.id])[event.id]
    assert summary.photo_count == 2
    assert summary.cover_id == dragged_to_front.id
    assert summary.cover_type == "photo"
    assert dragged_to_front.id > first_uploaded.id  # so id order disagrees


def test_cover_falls_back_to_id_when_orders_tie(db_session, event):
    # Media that predates any reordering all sits at 0, so the tiebreaker has
    # to keep the old behaviour rather than picking arbitrarily.
    a = _photo(event.id, 1, order=0)
    b = _photo(event.id, 2, order=0)
    db_session.add_all([a, b])
    db_session.commit()

    summary = _media_summaries(db_session, [event.id])[event.id]
    assert summary.cover_id == min(a.id, b.id)


def test_a_video_can_be_the_cover(db_session, event):
    """A clip opens an event the same way a photo can — the card shows its
    poster rather than skipping to the first photo."""
    db_session.add_all([_photo(event.id, 1, order=10), _video(event.id, order=5)])
    db_session.commit()

    summary = _media_summaries(db_session, [event.id])[event.id]
    assert summary.cover_type == "video"
    assert summary.media_count == 2
    # The photo count still counts photos; the badge uses media_count.
    assert summary.photo_count == 1


def test_an_event_with_only_videos_is_not_empty(db_session, event):
    # photo_count alone would be 0 and the card would render its empty state
    # for an event that plainly has content.
    db_session.add(_video(event.id, order=0))
    db_session.commit()

    summary = _media_summaries(db_session, [event.id])[event.id]
    assert summary.media_count == 1
    assert summary.cover_type == "video"


def test_failed_videos_are_not_counted_or_shown_as_the_cover(db_session, event):
    # A failed row holds nothing to display, so counting it would have the
    # card promise media it cannot show.
    failed = _video(event.id, order=0)
    failed.status = VideoStatus.FAILED
    db_session.add_all([failed, _photo(event.id, 1, order=10)])
    db_session.commit()

    summary = _media_summaries(db_session, [event.id])[event.id]
    assert summary.media_count == 1
    assert summary.cover_type == "photo"


def test_a_video_still_transcoding_does_not_become_the_cover(db_session, event):
    """It has no poster frame yet, so pointing the card at one would render a
    broken image until the transcode lands."""
    processing = _video(event.id, order=0)
    processing.status = VideoStatus.PROCESSING
    processing.filename = None
    processing.poster_filename = None
    db_session.add_all([processing, _photo(event.id, 1, order=10)])
    db_session.commit()

    summary = _media_summaries(db_session, [event.id])[event.id]
    assert summary.cover_type == "photo"
    # It is still part of the event, so the card counts it.
    assert summary.media_count == 2


def test_a_youtube_cover_carries_its_id_for_the_thumbnail(db_session, event):
    # Its thumbnail lives on YouTube's CDN; without the id the card would ask
    # our poster endpoint for a file that does not exist.
    link = EventVideo(
        event_id=event.id,
        kind=VideoKind.YOUTUBE,
        status=VideoStatus.READY,
        sort_order=0,
        youtube_id="dQw4w9WgXcQ",
    )
    db_session.add(link)
    db_session.commit()

    summary = _media_summaries(db_session, [event.id])[event.id]
    assert summary.cover_type == "video"
    assert summary.cover_youtube_id == "dQw4w9WgXcQ"


def test_an_event_whose_only_media_is_transcoding_has_no_cover(db_session, event):
    # Nothing to show yet, so the card renders its empty state rather than a
    # broken thumbnail — but the count tells the uploader it arrived.
    processing = _video(event.id, order=0)
    processing.status = VideoStatus.PROCESSING
    processing.filename = None
    processing.poster_filename = None
    db_session.add(processing)
    db_session.commit()

    summary = _media_summaries(db_session, [event.id])[event.id]
    assert summary.cover_type is None
    assert summary.cover_id is None
    assert summary.media_count == 1


def test_new_media_lands_after_what_is_already_there(db_session, event):
    """An upload used to take the column default of 0, which put it at the
    front of an event someone had already arranged — and a photo sorts ahead
    of a video at an equal position, so it also stole a clip's cover."""
    db_session.add_all([_photo(event.id, 1, order=0), _video(event.id, order=1)])
    db_session.commit()

    assert next_sort_order(db_session, event.id) == 2


def test_the_next_position_spans_both_tables(db_session, event):
    # One sequence covers photos and videos, so looking at only one table
    # would hand out a position that is already taken.
    db_session.add(_video(event.id, order=7))
    db_session.commit()

    assert next_sort_order(db_session, event.id) == 8


def test_the_first_item_of_an_empty_event_gets_a_position(db_session, event):
    # Nothing to come after; it just has to be a valid position.
    assert next_sort_order(db_session, event.id) >= 0


def test_an_appended_photo_does_not_take_over_a_video_cover(db_session, event):
    """The whole point: arrange a clip as the cover, add a photo, and the
    cover stays where it was put."""
    db_session.add_all([_video(event.id, order=0), _photo(event.id, 1, order=1)])
    db_session.commit()

    added = _photo(event.id, 2, order=next_sort_order(db_session, event.id))
    db_session.add(added)
    db_session.commit()

    summary = _media_summaries(db_session, [event.id])[event.id]
    assert summary.cover_type == "video"
    assert summary.cover_id != added.id
