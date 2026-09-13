"""Where an event's photos and videos live on disk.

Photos, videos, the event-delete handler and the startup sweep all need to
resolve the same directory. It used to live in the photos router, so the
events router imported it from there and the videos router would have had to
as well — routers reaching into each other for a path helper, and the sweep
that runs before the app starts pulling in FastAPI routing to get it.
"""

from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import EventPhoto, EventVideo


def event_uploads_dir(uploads_root: Path, event_id: int) -> Path:
    """Per-event media directory under the shared uploads tree."""
    return uploads_root / "events" / str(event_id)


def video_files(video: EventVideo, uploads_root: Path) -> list[Path]:
    """Every on-disk file a video row could own, for deletion and cleanup.

    Derived from the id rather than from what the row recorded, because the
    interesting case is exactly when those disagree: a transcode killed
    partway through leaves a half-written .mp4 while filename is still null,
    since that column is only set on success. Going by the row would walk
    straight past the orphan. The names are a fixed convention, so listing
    them unconditionally costs nothing and misses nothing.

    The .src staging upload is included for the same reason — normally gone
    by the time a row is READY, and the copy worth hundreds of megabytes when
    it is not.
    """
    event_dir = event_uploads_dir(uploads_root, video.event_id)
    names = {
        f"{video.id}.mp4",
        f"{video.id}.jpg",
        f"{video.id}.src",
        video.filename,
        video.poster_filename,
    }
    return [event_dir / name for name in sorted(n for n in names if n)]


def next_sort_order(db: Session, event_id: int) -> int:
    """Where a newly added photo or video belongs: after everything else.

    The column defaults to 0, which dropped every upload at the *front* of an
    event whose media had been arranged — and, because a photo sorts ahead of
    a video at an equal position, let one new photo take over a cover the
    editor had deliberately set to a clip.

    One sequence spans both tables, so the next position has to consider both.
    """
    highest = max(
        db.query(func.max(EventPhoto.sort_order))
        .filter(EventPhoto.event_id == event_id)
        .scalar()
        or 0,
        db.query(func.max(EventVideo.sort_order))
        .filter(EventVideo.event_id == event_id)
        .scalar()
        or 0,
    )
    return highest + 1
