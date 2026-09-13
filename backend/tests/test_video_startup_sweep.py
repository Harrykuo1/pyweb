from datetime import UTC, date, datetime, timedelta

import pytest

from app.init_db import FAILED_VIDEO_RETENTION_DAYS, sweep_interrupted_videos
from app.models import (
    Event,
    EventVideo,
    PostStatus,
    User,
    UserRole,
    VideoKind,
    VideoStatus,
)


@pytest.fixture
def event(db_session):
    user = User(role=UserRole.MEMBER, discord_id="900")
    db_session.add(user)
    db_session.flush()
    ev = Event(
        id=1,
        title="社遊",
        event_date=date(2026, 3, 1),
        author_user_id=user.id,
        status=PostStatus.ACCEPTED,
    )
    db_session.add(ev)
    db_session.flush()
    return ev


def _files_for(uploads_dir, video_id):
    event_dir = uploads_dir / "events" / "1"
    event_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        event_dir / f"{video_id}.mp4",
        event_dir / f"{video_id}.jpg",
        event_dir / f"{video_id}.src",
    ]
    for p in paths:
        p.write_bytes(b"x" * 10)
    return paths


def test_a_transcode_interrupted_by_a_restart_is_marked_failed(
    db_session, event, tmp_path
):
    """Transcoding runs in-process, so a container stop kills it outright.
    Every PROCESSING row seen at startup is orphaned by definition — there is
    no process left that could still be working on it."""
    video = EventVideo(
        event_id=event.id,
        kind=VideoKind.UPLOAD,
        status=VideoStatus.PROCESSING,
        filename="1.mp4",
        poster_filename="1.jpg",
        processing_started_at=datetime.now(UTC),
    )
    db_session.add(video)
    db_session.commit()
    paths = _files_for(tmp_path, video.id)

    sweep_interrupted_videos(db_session, tmp_path)

    db_session.refresh(video)
    assert video.status is VideoStatus.FAILED
    assert video.failed_at is not None
    # Nothing to serve, so nothing should claim otherwise.
    assert video.filename is None
    assert video.poster_filename is None
    # The half-written MP4 plus the original upload is hundreds of MB that
    # the nightly backup would otherwise keep carrying.
    assert [p for p in paths if p.exists()] == []


def test_the_row_survives_so_the_uploader_learns_why(db_session, event, tmp_path):
    # An upload that silently disappears leaves the uploader unable to tell
    # whether it ever happened; a failed row tells them to retry.
    video = EventVideo(
        event_id=event.id, kind=VideoKind.UPLOAD, status=VideoStatus.PROCESSING
    )
    db_session.add(video)
    db_session.commit()

    sweep_interrupted_videos(db_session, tmp_path)

    assert db_session.query(EventVideo).count() == 1
    assert "重新上傳" in db_session.query(EventVideo).one().error_detail


def test_stale_failures_are_purged_but_recent_ones_are_kept(
    db_session, event, tmp_path
):
    now = datetime.now(UTC)
    old = EventVideo(
        event_id=event.id,
        kind=VideoKind.UPLOAD,
        status=VideoStatus.FAILED,
        failed_at=now - timedelta(days=FAILED_VIDEO_RETENTION_DAYS + 1),
    )
    recent = EventVideo(
        event_id=event.id,
        kind=VideoKind.UPLOAD,
        status=VideoStatus.FAILED,
        failed_at=now - timedelta(days=1),
    )
    db_session.add_all([old, recent])
    db_session.commit()
    old_id, recent_id = old.id, recent.id
    old_paths = _files_for(tmp_path, old_id)

    sweep_interrupted_videos(db_session, tmp_path)

    remaining = {v.id for v in db_session.query(EventVideo).all()}
    assert remaining == {recent_id}
    assert [p for p in old_paths if p.exists()] == []


def test_ready_videos_are_left_alone(db_session, event, tmp_path):
    video = EventVideo(
        event_id=event.id,
        kind=VideoKind.UPLOAD,
        status=VideoStatus.READY,
        filename="1.mp4",
        poster_filename="1.jpg",
    )
    db_session.add(video)
    db_session.commit()
    paths = _files_for(tmp_path, video.id)

    sweep_interrupted_videos(db_session, tmp_path)

    db_session.refresh(video)
    assert video.status is VideoStatus.READY
    assert video.filename == "1.mp4"
    assert all(p.exists() for p in paths)
