from datetime import UTC, datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import (
    require_admin_password,
    require_completed_member,
    require_posting_member,
)
from app.core.event_media import (
    event_uploads_dir,
    next_sort_order,
    video_files,
)
from app.core.media import (
    MediaConversionError,
    extract_poster,
    probe_duration_seconds,
    transcode_video,
)
from app.core.post_visibility import visible_event_or_404
from app.core.runtime_config import get_int
from app.core.uploads import stream_to_disk
from app.core.youtube import parse_video_id
from app.database import SessionLocal, get_db
from app.models import (
    Event,
    EventPhoto,
    EventVideo,
    User,
    UserRole,
    VideoKind,
    VideoStatus,
)
from app.schemas import (
    EventVideoCaptionUpdate,
    EventVideoLinkCreate,
    EventVideoResponse,
    MediaOrderUpdate,
    PasswordConfirmRequest,
)

router = APIRouter(prefix="/api/events", tags=["event_videos"])

# Anything a phone or camera produces. The container says nothing about the
# codec inside — an .mp4 may hold HEVC — which is why every upload is
# transcoded rather than probed and conditionally passed through.
VIDEO_MIME_PREFIXES = ("video/",)

# Far enough in to clear the black frames while a phone's sensor settles,
# close enough to still exist in a very short clip.
POSTER_SEEK_SECONDS = 1


def get_uploads_root() -> Path:
    """FastAPI dependency that resolves the configured uploads root.

    Exposed so tests can override it via ``app.dependency_overrides``,
    matching the photos / attachments routers."""
    return Path(settings.uploads_dir)


def _require_event_editor(event: Event, user: User) -> None:
    # Same rule as photos: an admin, or the event's own author.
    if user.role is UserRole.ADMIN:
        return
    if event.author_user_id is None or event.author_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your post"
        )


def _can_see_failures(event: Event, user: User) -> bool:
    """Whether this viewer should see rows that never produced a video.

    Only the people who could have uploaded it: a failed row is a message to
    whoever needs to retry, not content for the event page.
    """
    return user.role is UserRole.ADMIN or (
        event.author_user_id is not None and event.author_user_id == user.id
    )


def _serialize(video: EventVideo, *, is_admin: bool) -> EventVideoResponse:
    return EventVideoResponse(
        id=video.id,
        event_id=video.event_id,
        kind=video.kind.value,
        status=video.status.value,
        caption=video.caption,
        uploaded_at=video.uploaded_at,
        sort_order=video.sort_order,
        duration_seconds=video.duration_seconds,
        size_bytes=video.size_bytes,
        has_poster=video.poster_filename is not None,
        youtube_id=video.youtube_id,
        # ffmpeg's message names paths and codec parameters; the uploader
        # gets "it failed, try again", an admin gets something debuggable.
        error_detail=video.error_detail if is_admin else None,
    )


def _get_video_or_404(db: Session, event_id: int, video_id: int) -> EventVideo:
    video = db.query(EventVideo).filter_by(id=video_id, event_id=event_id).one_or_none()
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到影片")
    return video


def transcode_in_background(video_id: int, source: Path, uploads_root: Path) -> None:
    """Turn an uploaded file into a playable MP4 plus a poster frame.

    Runs after the response has been sent, on its own session — the request's
    is long closed by then. Everything is written before the row is flipped to
    READY, so a viewer never sees a status that promises a file which is not
    there yet.
    """
    db = SessionLocal()
    try:
        video = db.query(EventVideo).filter_by(id=video_id).one_or_none()
        if video is None:  # deleted while it sat in the queue
            source.unlink(missing_ok=True)
            return

        event_dir = event_uploads_dir(uploads_root, video.event_id)
        target = event_dir / f"{video.id}.mp4"
        poster = event_dir / f"{video.id}.jpg"
        try:
            duration = probe_duration_seconds(source)
            transcode_video(source, target)
            extract_poster(
                target,
                poster,
                at_second=min(POSTER_SEEK_SECONDS, max(duration - 1, 0)),
            )
            video.filename = target.name
            video.poster_filename = poster.name
            video.size_bytes = target.stat().st_size
            video.duration_seconds = duration
            video.status = VideoStatus.READY
            video.error_detail = None
        except MediaConversionError as e:
            # The original is never kept: it is the unplayable form, and a
            # failed row exists to tell someone to retry, not to store bytes.
            target.unlink(missing_ok=True)
            poster.unlink(missing_ok=True)
            video.status = VideoStatus.FAILED
            video.failed_at = datetime.now(UTC)
            video.error_detail = str(e)
        db.commit()
    finally:
        source.unlink(missing_ok=True)
        db.close()


@router.get("/{event_id}/videos", response_model=list[EventVideoResponse])
def list_videos(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
) -> list[EventVideoResponse]:
    event = visible_event_or_404(db, event_id, current_user)
    query = db.query(EventVideo).filter_by(event_id=event_id)
    if not _can_see_failures(event, current_user):
        query = query.filter(EventVideo.status != VideoStatus.FAILED)
    is_admin = current_user.role is UserRole.ADMIN
    return [
        _serialize(v, is_admin=is_admin)
        for v in query.order_by(EventVideo.sort_order.asc(), EventVideo.id.asc()).all()
    ]


@router.post(
    "/{event_id}/videos",
    response_model=EventVideoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_video(
    event_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    caption: str | None = Form(default=None),
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    current_user: User = Depends(require_posting_member),
) -> EventVideoResponse:
    event = visible_event_or_404(db, event_id, current_user)
    _require_event_editor(event, current_user)

    if not (file.content_type or "").startswith(VIDEO_MIME_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="請上傳影片檔",
        )

    # A failed row holds nothing, so counting it would let three bad uploads
    # lock someone out of a limit they never actually used.
    max_count = get_int(db, "max_videos_per_event")
    current_count = (
        db.query(EventVideo)
        .filter(
            EventVideo.event_id == event_id,
            EventVideo.status != VideoStatus.FAILED,
        )
        .count()
    )
    if current_count >= max_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"影片數量已達上限（最多 {max_count} 支）",
        )

    max_mb = get_int(db, "max_video_mb")
    trimmed_caption = caption.strip() if caption else ""

    video = EventVideo(
        event_id=event_id,
        kind=VideoKind.UPLOAD,
        status=VideoStatus.PROCESSING,
        caption=trimmed_caption or None,
        uploaded_at=datetime.now(UTC),
        processing_started_at=datetime.now(UTC),
        sort_order=next_sort_order(db, event_id),
    )
    db.add(video)
    db.flush()

    source = event_uploads_dir(uploads_root, event_id) / f"{video.id}.src"
    try:
        await stream_to_disk(
            file,
            source,
            max_bytes=max_mb * 1024 * 1024,
            too_large_detail=f"影片大小超過 {max_mb} MB 上限",
        )
    except BaseException:
        db.rollback()
        raise

    event.mark_edited(current_user.id)
    db.commit()
    db.refresh(video)
    # Queued rather than awaited: transcoding runs at roughly half to one
    # times the clip's length, which no browser upload would survive waiting
    # for. The client polls the list endpoint until the status flips.
    background_tasks.add_task(transcode_in_background, video.id, source, uploads_root)
    return _serialize(video, is_admin=current_user.role is UserRole.ADMIN)


@router.post(
    "/{event_id}/videos/youtube",
    response_model=EventVideoResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_youtube_video(
    event_id: int,
    payload: EventVideoLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> EventVideoResponse:
    """Reference a video on YouTube instead of hosting one.

    Costs no storage and no transcoding, which is what makes it the answer
    for anything longer than the upload cap allows. Only the parsed id is
    kept — the pasted URL is never stored and never echoed back into an
    iframe.
    """
    event = visible_event_or_404(db, event_id, current_user)
    _require_event_editor(event, current_user)

    video_id = parse_video_id(payload.url)
    if video_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="請貼上有效的 YouTube 連結",
        )

    max_count = get_int(db, "max_videos_per_event")
    current_count = (
        db.query(EventVideo)
        .filter(
            EventVideo.event_id == event_id,
            EventVideo.status != VideoStatus.FAILED,
        )
        .count()
    )
    if current_count >= max_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"影片數量已達上限（最多 {max_count} 支）",
        )

    caption = payload.caption.strip() if payload.caption else ""
    video = EventVideo(
        event_id=event_id,
        kind=VideoKind.YOUTUBE,
        # Nothing to transcode, so it is watchable the moment it is saved.
        status=VideoStatus.READY,
        youtube_id=video_id,
        caption=caption or None,
        uploaded_at=datetime.now(UTC),
        sort_order=next_sort_order(db, event_id),
    )
    db.add(video)
    event.mark_edited(current_user.id)
    db.commit()
    db.refresh(video)
    return _serialize(video, is_admin=current_user.role is UserRole.ADMIN)


@router.put("/{event_id}/media/order", status_code=status.HTTP_204_NO_CONTENT)
def reorder_media(
    event_id: int,
    payload: MediaOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> Response:
    """Rewrite the whole media order for one event.

    Photos and videos live in separate tables but share one sequence, so the
    request carries the complete order rather than a move. Renumbering
    everything in a single transaction is what keeps the two halves from
    drifting apart; a partial update could leave them describing different
    orders with no way to tell which was right.

    Anything the client omitted keeps its position after the listed items,
    so a stale client cannot silently drop media it did not know about.
    """
    event = visible_event_or_404(db, event_id, current_user)
    _require_event_editor(event, current_user)

    photos = {p.id: p for p in db.query(EventPhoto).filter_by(event_id=event_id)}
    videos = {v.id: v for v in db.query(EventVideo).filter_by(event_id=event_id)}

    seen: set[tuple[str, int]] = set()
    position = 0
    for item in payload.items:
        target = photos.get(item.id) if item.type == "photo" else videos.get(item.id)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到{'照片' if item.type == 'photo' else '影片'}",
            )
        key = (item.type, item.id)
        if key in seen:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="順序中有重複的項目",
            )
        seen.add(key)
        target.sort_order = position
        position += 1

    # Media uploaded between the client's read and this write is not in the
    # list; it keeps a position after everything ordered rather than being
    # renumbered to the front.
    # Media uploaded between the client's read and this write is not in the
    # list; it keeps a position after everything ordered rather than being
    # renumbered to the front.
    for kind, rows in (("photo", photos.values()), ("video", videos.values())):
        for row in rows:
            if (kind, row.id) not in seen:
                row.sort_order = position
                position += 1

    event.mark_edited(current_user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{event_id}/videos/{video_id}/file")
def get_video_file(
    event_id: int,
    video_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    current_user: User = Depends(require_completed_member),
) -> Response:
    visible_event_or_404(db, event_id, current_user)
    video = _get_video_or_404(db, event_id, video_id)
    if video.status is not VideoStatus.READY or not video.filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="影片尚未就緒"
        )
    path = event_uploads_dir(uploads_root, event_id) / video.filename
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="影片檔案不存在"
        )
    # FileResponse honours Range requests, which is what lets the player seek
    # instead of downloading the whole file before the scrubber works.
    return FileResponse(
        path,
        media_type="video/mp4",
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{event_id}/videos/{video_id}/poster")
def get_video_poster(
    event_id: int,
    video_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    current_user: User = Depends(require_completed_member),
) -> Response:
    visible_event_or_404(db, event_id, current_user)
    video = _get_video_or_404(db, event_id, video_id)
    if not video.poster_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="找不到影片封面"
        )
    path = event_uploads_dir(uploads_root, event_id) / video.poster_filename
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="找不到影片封面"
        )
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put("/{event_id}/videos/{video_id}", response_model=EventVideoResponse)
def update_video_caption(
    event_id: int,
    video_id: int,
    payload: EventVideoCaptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> EventVideoResponse:
    event = visible_event_or_404(db, event_id, current_user)
    _require_event_editor(event, current_user)
    video = _get_video_or_404(db, event_id, video_id)
    caption = payload.caption.strip() if payload.caption else ""
    video.caption = caption or None
    event.mark_edited(current_user.id)
    db.commit()
    db.refresh(video)
    return _serialize(video, is_admin=current_user.role is UserRole.ADMIN)


@router.delete(
    "/{event_id}/videos/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_video(
    event_id: int,
    video_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    current_user: User = Depends(require_posting_member),
    payload: PasswordConfirmRequest | None = None,
) -> Response:
    event = visible_event_or_404(db, event_id, current_user)
    _require_event_editor(event, current_user)
    video = _get_video_or_404(db, event_id, video_id)
    # Same confirmation as photos. They sit in one grid with one delete
    # button each, so two buttons that look identical and behave differently
    # is the wrong kind of surprise. The author still deletes without a
    # password; only an admin acting on someone else's event re-authenticates.
    if current_user.role is UserRole.ADMIN:
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password is required",
            )
        require_admin_password(db, payload.password)
    for path in video_files(video, uploads_root):
        path.unlink(missing_ok=True)
    db.delete(video)
    event.mark_edited(current_user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
