from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

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
from starlette.concurrency import run_in_threadpool

from app.core.attachments import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    ext_of,
    next_available_filename,
    sanitize_filename,
)
from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.core import office_convert
from app.core.runtime_config import get_int
from app.database import get_db
from app.models import Job, JobAttachment, User
from app.schemas import JobAttachmentResponse


def job_uploads_dir(uploads_root: Path, job_id: int) -> Path:
    """Per-job attachment directory.

    Sitting under a "jobs/" subtree leaves the top of uploads_root
    free for future upload categories (members/, projects/, ...)
    without fighting for the numeric-id namespace at the root.
    """
    return uploads_root / "jobs" / str(job_id)


def _preview_path(uploads_root: Path, job_id: int, filename: str) -> Path:
    return job_uploads_dir(uploads_root, job_id) / f"{filename}.preview.pdf"


def _serialize(
    attachment: JobAttachment, uploads_root: Path
) -> JobAttachmentResponse:
    return JobAttachmentResponse(
        id=attachment.id,
        job_id=attachment.job_id,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        uploaded_at=attachment.uploaded_at,
        preview_available=_preview_path(
            uploads_root, attachment.job_id, attachment.filename
        ).exists(),
    )

router = APIRouter(prefix="/api/jobs", tags=["job_attachments"])


def get_uploads_root() -> Path:
    """FastAPI dependency that resolves the configured uploads root.

    Exposed so tests can override it via ``app.dependency_overrides``
    instead of monkey-patching the settings module — the same swap
    pattern already used for the DB session."""
    return Path(settings.uploads_dir)


ConflictStrategy = Literal["rename", "overwrite"]


def _get_job_or_404(db: Session, job_id: int) -> Job:
    job = db.query(Job).filter_by(id=job_id).one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到求職紀錄",
        )
    return job


@router.post(
    "/{job_id}/attachments",
    response_model=JobAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    job_id: int,
    file: UploadFile = File(...),
    conflict_strategy: Annotated[ConflictStrategy | None, Form()] = None,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    _: User = Depends(require_admin),
) -> JobAttachmentResponse:
    _get_job_or_404(db, job_id)

    try:
        clean_name = sanitize_filename(file.filename or "")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )

    ext = ext_of(clean_name)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"不支援的副檔名：{ext}",
        )

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"不支援的檔案類型：{file.content_type}",
        )

    # Conflict detection runs before reading the body so the rejected
    # case doesn't waste bandwidth re-uploading on every retry. The
    # frontend should preflight against the attachment list, but a
    # 409 here is the authoritative fallback.
    upload_dir = job_uploads_dir(uploads_root, job_id)
    target_path = upload_dir / clean_name
    existing_row = (
        db.query(JobAttachment)
        .filter_by(job_id=job_id, filename=clean_name)
        .one_or_none()
    )
    has_conflict = existing_row is not None or target_path.exists()

    if has_conflict and conflict_strategy is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "filename_conflict",
                "conflicting_filename": clean_name,
            },
        )

    max_mb = get_int(db, "max_attachment_mb")
    max_bytes = max_mb * 1024 * 1024
    data = await file.read()
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"檔案大小超過 {max_mb} MB 上限",
        )

    # Count check only matters when a new row would be added.
    # Overwrite reuses the existing row, so it doesn't push the count up.
    creates_new_row = not (has_conflict and conflict_strategy == "overwrite")
    if creates_new_row:
        max_count = get_int(db, "max_attachments_per_job")
        current_count = (
            db.query(JobAttachment).filter_by(job_id=job_id).count()
        )
        if current_count >= max_count:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"附件數量已達上限（最多 {max_count} 個）",
            )

    upload_dir.mkdir(parents=True, exist_ok=True)

    if has_conflict and conflict_strategy == "rename":
        final_filename = next_available_filename(upload_dir, clean_name)
    else:
        final_filename = clean_name

    final_path = upload_dir / final_filename
    final_path.write_bytes(data)

    # Re-generate the on-disk PDF preview alongside the saved file so
    # the in-page Office viewer doesn't depend on a separate job. The
    # overwrite case explicitly nukes the stale preview first; a failed
    # conversion just leaves preview_available=False and the frontend
    # falls back to a download link.
    preview_target = _preview_path(uploads_root, job_id, final_filename)
    if preview_target.exists():
        preview_target.unlink()
    if office_convert.is_convertible(final_filename):
        # Push the blocking subprocess+polling work off the event loop
        # — otherwise OnlyOffice's source-fetch GET ends up waiting on
        # the same uvicorn loop that's busy polling OnlyOffice, and the
        # whole pipeline deadlocks until OnlyOffice times out.
        await run_in_threadpool(
            office_convert.convert_to_pdf, job_id, final_path, preview_target
        )

    now = datetime.now(timezone.utc)
    if has_conflict and conflict_strategy == "overwrite" and existing_row is not None:
        existing_row.mime_type = file.content_type or existing_row.mime_type
        existing_row.size_bytes = len(data)
        existing_row.uploaded_at = now
        db.commit()
        db.refresh(existing_row)
        return _serialize(existing_row, uploads_root)

    new_row = JobAttachment(
        job_id=job_id,
        filename=final_filename,
        mime_type=file.content_type,
        size_bytes=len(data),
        uploaded_at=now,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return _serialize(new_row, uploads_root)


def _content_disposition(filename: str, disposition: str = "inline") -> str:
    """Build a Content-Disposition header that survives non-ASCII filenames.

    ASCII names use the legacy ``filename=`` form, which every browser
    understands; non-ASCII names additionally emit RFC 5987's
    ``filename*=UTF-8''<percent-encoded>`` so the real characters land
    on modern browsers instead of being mojibake'd. Raw non-ASCII bytes
    in the legacy form would explode against the latin-1 HTTP header
    encoding, so we replace them with underscores in the fallback."""
    encoded = quote(filename, safe="")
    try:
        filename.encode("ascii")
    except UnicodeEncodeError:
        ascii_safe = "".join(c if ord(c) < 128 else "_" for c in filename)
        return f"{disposition}; filename=\"{ascii_safe}\"; filename*=UTF-8''{encoded}"
    return f"{disposition}; filename=\"{filename}\""


def _get_attachment_or_404(
    db: Session, job_id: int, attachment_id: int
) -> JobAttachment:
    row = (
        db.query(JobAttachment)
        .filter_by(id=attachment_id, job_id=job_id)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到附件",
        )
    return row


@router.get(
    "/{job_id}/attachments",
    response_model=list[JobAttachmentResponse],
)
def list_attachments(
    job_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    _: User = Depends(get_current_user),
) -> list[JobAttachmentResponse]:
    _get_job_or_404(db, job_id)
    rows = (
        db.query(JobAttachment)
        .filter_by(job_id=job_id)
        .order_by(JobAttachment.uploaded_at.asc(), JobAttachment.id.asc())
        .all()
    )
    return [_serialize(r, uploads_root) for r in rows]


@router.get("/{job_id}/attachments/{attachment_id}")
def download_attachment(
    job_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    _: User = Depends(get_current_user),
) -> FileResponse:
    attachment = _get_attachment_or_404(db, job_id, attachment_id)

    file_path = job_uploads_dir(uploads_root, job_id) / attachment.filename
    if not file_path.exists():
        # DB row points at a missing file — surface a clean 404 instead
        # of a 500 from FileResponse trying to stat a non-existent path.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="附件檔案不存在",
        )

    return FileResponse(
        file_path,
        media_type=attachment.mime_type,
        # Inline so PDFs and images render in <embed>/<img> previews;
        # the frontend's <a download="..."> still forces a save when the
        # user clicks an explicit download link.
        headers={"Content-Disposition": _content_disposition(attachment.filename)},
    )


@router.get("/{job_id}/attachments/{attachment_id}/preview")
def preview_attachment(
    job_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    _: User = Depends(get_current_user),
) -> FileResponse:
    attachment = _get_attachment_or_404(db, job_id, attachment_id)

    preview_path = _preview_path(uploads_root, job_id, attachment.filename)
    if not preview_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="此附件沒有可預覽的版本",
        )

    return FileResponse(
        preview_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": _content_disposition(
                f"{attachment.filename}.pdf"
            )
        },
    )


@router.delete(
    "/{job_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_attachment(
    job_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    _: User = Depends(require_admin),
) -> Response:
    attachment = _get_attachment_or_404(db, job_id, attachment_id)

    job_dir = job_uploads_dir(uploads_root, job_id)
    file_path = job_dir / attachment.filename
    preview_path = _preview_path(uploads_root, job_id, attachment.filename)
    # Remove on-disk artefacts before the DB row so a successful DB
    # delete can't leave orphan blobs behind. If a file is already
    # gone (manual cleanup, partial crash), keep going.
    if file_path.exists():
        file_path.unlink()
    if preview_path.exists():
        preview_path.unlink()

    # If that was the last file in the per-job directory, clean the
    # directory up so the host filesystem doesn't accumulate empty
    # shells. rmdir refuses non-empty dirs, so a stray file (e.g. a
    # manual drop) keeps the directory alive on purpose.
    try:
        job_dir.rmdir()
    except OSError:
        pass

    db.delete(attachment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
