from datetime import UTC, datetime
from pathlib import Path

from fastapi import (
    APIRouter,
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
from app.core.uploads import stream_to_disk
from app.database import get_db
from app.models import Event, EventPhoto, User, UserRole
from app.schemas import (
    EventPhotoCaptionUpdate,
    EventPhotoResponse,
    PasswordConfirmRequest,
)

router = APIRouter(prefix="/api/events", tags=["event_photos"])

PHOTO_MAX_BYTES = 8 * 1024 * 1024
MAX_PHOTOS_PER_EVENT = 30
# Mirror the member-photo allowlist plus GIF, which is common for event
# snapshots. Each maps to the canonical extension we store on disk.
PHOTO_MIME_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def get_uploads_root() -> Path:
    """FastAPI dependency that resolves the configured uploads root.

    Exposed so tests can override it via ``app.dependency_overrides``,
    matching the members / job_attachments routers."""
    return Path(settings.uploads_dir)


def event_uploads_dir(uploads_root: Path, event_id: int) -> Path:
    """Per-event photo directory under the shared uploads tree."""
    return uploads_root / "events" / str(event_id)


def _get_event_or_404(db: Session, event_id: int) -> Event:
    event = db.query(Event).filter_by(id=event_id).one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到活動")
    return event


def _require_event_editor(event: Event, user: User) -> None:
    # Same ownership rule as events.py update/delete: an admin, or the
    # event's own author, may manage its photos.
    if user.role is UserRole.ADMIN:
        return
    if event.author_user_id is None or event.author_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your post"
        )


def _get_photo_or_404(db: Session, event_id: int, photo_id: int) -> EventPhoto:
    photo = db.query(EventPhoto).filter_by(id=photo_id, event_id=event_id).one_or_none()
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到照片")
    return photo


@router.get("/{event_id}/photos", response_model=list[EventPhotoResponse])
def list_photos(
    event_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_completed_member),
) -> list[EventPhoto]:
    _get_event_or_404(db, event_id)
    return (
        db.query(EventPhoto)
        .filter_by(event_id=event_id)
        .order_by(EventPhoto.id.asc())
        .all()
    )


@router.get("/{event_id}/photos/{photo_id}")
async def get_photo(
    event_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    _: object = Depends(require_completed_member),
) -> Response:
    photo = _get_photo_or_404(db, event_id, photo_id)
    file_path = event_uploads_dir(uploads_root, event_id) / photo.filename
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="照片檔案不存在"
        )
    return FileResponse(
        file_path,
        media_type=photo.mime_type or "application/octet-stream",
        headers={
            # The photo bytes for a given id never change (a re-upload
            # creates a new row with a new id), so the URL is effectively
            # content-addressed — cache it hard and skip revalidation.
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/{event_id}/photos",
    response_model=EventPhotoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_photo(
    event_id: int,
    file: UploadFile = File(...),
    caption: str | None = Form(default=None),
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    current_user: User = Depends(require_posting_member),
) -> EventPhoto:
    event = _get_event_or_404(db, event_id)
    _require_event_editor(event, current_user)

    if file.content_type not in PHOTO_MIME_TO_EXT:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"照片格式僅支援 {sorted(PHOTO_MIME_TO_EXT)}",
        )

    current_count = db.query(EventPhoto).filter_by(event_id=event_id).count()
    if current_count >= MAX_PHOTOS_PER_EVENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"照片數量已達上限（最多 {MAX_PHOTOS_PER_EVENT} 張）",
        )

    trimmed_caption = caption.strip() if caption else ""
    # Flush an empty-filename row first so the auto-assigned id can name
    # the on-disk file — keeps every photo's path stable and collision-free
    # under the per-event directory. size_bytes is backfilled once the
    # stream lands, since nothing knows the real size until then.
    photo = EventPhoto(
        event_id=event_id,
        filename="",
        mime_type=file.content_type,
        size_bytes=0,
        caption=trimmed_caption or None,
        uploaded_at=datetime.now(UTC),
    )
    db.add(photo)
    db.flush()

    ext = PHOTO_MIME_TO_EXT[file.content_type]
    photo.filename = f"{photo.id}{ext}"
    target = event_uploads_dir(uploads_root, event_id) / photo.filename
    # The row had to be flushed before the bytes could land, so a rejected
    # upload has to undo it explicitly. Leaving it to the session's lifetime
    # would work in production and quietly not in anything that shares a
    # session, which is exactly where it would go unnoticed.
    try:
        photo.size_bytes = await stream_to_disk(
            file,
            target,
            max_bytes=PHOTO_MAX_BYTES,
            too_large_detail=(
                f"照片大小超過 {PHOTO_MAX_BYTES // (1024 * 1024)} MB 上限"
            ),
        )
    except BaseException:
        db.rollback()
        raise

    db.commit()
    db.refresh(photo)
    return photo


@router.put("/{event_id}/photos/{photo_id}", response_model=EventPhotoResponse)
def update_photo_caption(
    event_id: int,
    photo_id: int,
    payload: EventPhotoCaptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> EventPhoto:
    event = _get_event_or_404(db, event_id)
    _require_event_editor(event, current_user)
    photo = _get_photo_or_404(db, event_id, photo_id)
    caption = payload.caption.strip() if payload.caption else ""
    photo.caption = caption or None
    db.commit()
    db.refresh(photo)
    return photo


@router.delete(
    "/{event_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_photo(
    event_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    current_user: User = Depends(require_posting_member),
    payload: PasswordConfirmRequest | None = None,
) -> Response:
    event = _get_event_or_404(db, event_id)
    _require_event_editor(event, current_user)
    if current_user.role is UserRole.ADMIN:
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password is required",
            )
        require_admin_password(db, payload.password)
    photo = _get_photo_or_404(db, event_id, photo_id)

    event_dir = event_uploads_dir(uploads_root, event_id)
    file_path = event_dir / photo.filename
    if file_path.exists():
        file_path.unlink()

    db.delete(photo)
    db.commit()

    # Reap the per-event directory once its last photo is gone.
    try:
        event_dir.rmdir()
    except OSError:
        pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)
