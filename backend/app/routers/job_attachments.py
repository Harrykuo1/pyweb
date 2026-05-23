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
    PREVIEW_INLINE_EXTENSIONS,
    ext_of,
    is_junk,
    next_available_relpath,
    sanitize_relpath,
)
from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.core import office_convert
from app.core.runtime_config import get_int
from app.core.security import verify_password
from app.database import get_db
from app.models import Job, JobAttachment, User
from app.schemas import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    JobAttachmentResponse,
    PasswordConfirmRequest,
)


def _require_admin_password(password: str, admin: User) -> None:
    """Re-authenticate the admin before a destructive attachment action.

    Returns 422 (not 401) on mismatch so the global axios auth-interceptor
    doesn't read a typo'd confirmation password as an expired session and
    bounce the user back to /login. Same rationale as members.py /
    jobs.py — keep the local request-validation failure local.
    """
    if not verify_password(password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Password is incorrect",
        )


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
    relative_path: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    _: User = Depends(require_admin),
) -> JobAttachmentResponse:
    _get_job_or_404(db, job_id)

    # Folder uploads send the in-folder relpath as a separate form
    # field — file.filename only has the basename, which would lose
    # the directory structure. Single-file uploads omit the field and
    # the basename becomes the relpath.
    raw_name = relative_path if relative_path else (file.filename or "")
    try:
        clean_name = sanitize_relpath(raw_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )

    if is_junk(clean_name):
        # Frontend already filters these out, but defence-in-depth.
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="不支援的檔案類型（系統暫存檔）",
        )

    # No extension / MIME allowlist: any binary the admin uploads is
    # stored as-is. The download endpoint serves non-previewable types
    # with Content-Disposition: attachment so HTML/SVG/script payloads
    # can't ride this response into an XSS surface.

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
        final_filename = next_available_relpath(upload_dir, clean_name)
    else:
        final_filename = clean_name

    final_path = upload_dir / final_filename
    # The relpath can have intermediate subdirectories (folder upload);
    # make sure they exist before write_bytes.
    final_path.parent.mkdir(parents=True, exist_ok=True)
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
            office_convert.convert_to_pdf,
            job_id,
            final_path,
            final_filename,
            preview_target,
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

    # Only the small preview-safe set gets Content-Disposition: inline
    # — that's what the viewer's <embed>/<img> tags rely on. Everything
    # else (Office sources, archives, source code, .html, .svg, ...) is
    # served as an attachment, with nosniff to keep browsers from
    # guessing the type and rendering it inline against our wishes.
    ext = ext_of(attachment.filename)
    disposition_mode = "inline" if ext in PREVIEW_INLINE_EXTENSIONS else "attachment"

    return FileResponse(
        file_path,
        media_type=attachment.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": _content_disposition(
                attachment.filename, disposition_mode
            ),
            "X-Content-Type-Options": "nosniff",
        },
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
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


def _prune_empty_subdirs(root: Path) -> None:
    """Bottom-up sweep: rmdir every empty descendant of `root`, leaving
    `root` itself for the caller to decide on. Bulk delete needs this
    because multiple files across the tree can disappear in one call,
    and the single-file handler's "walk up from one file's parent"
    isn't enough to find all the newly-empty directories elsewhere."""
    if not root.exists() or not root.is_dir():
        return
    for child in list(root.iterdir()):
        if child.is_dir():
            _prune_empty_subdirs(child)
            try:
                child.rmdir()
            except OSError:
                pass


@router.post(
    "/{job_id}/attachments/bulk-delete",
    response_model=BulkDeleteResponse,
)
def bulk_delete_attachments(
    job_id: int,
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    admin: User = Depends(require_admin),
) -> BulkDeleteResponse:
    """Delete every attachment whose id appears in the body. Scoped
    to a single job so a malicious or buggy client can't spray
    deletes across the table; rows whose job_id doesn't match are
    silently skipped (no leakage of which IDs exist where).

    Used both by the multi-select bulk action and by "delete this
    whole folder" — the frontend expands the folder into its
    descendant file IDs before sending."""
    _require_admin_password(payload.password, admin)
    rows = (
        db.query(JobAttachment)
        .filter(
            JobAttachment.job_id == job_id,
            JobAttachment.id.in_(payload.ids),
        )
        .all()
    )

    job_dir = job_uploads_dir(uploads_root, job_id)
    deleted = 0
    for row in rows:
        file_path = job_dir / row.filename
        preview_path = _preview_path(uploads_root, job_id, row.filename)
        if file_path.exists():
            file_path.unlink()
        if preview_path.exists():
            preview_path.unlink()
        db.delete(row)
        deleted += 1

    # Bulk delete can leave empty dirs anywhere across the tree;
    # one walk top-down then rmdir bottom-up handles the lot.
    _prune_empty_subdirs(job_dir)
    try:
        job_dir.rmdir()
    except OSError:
        pass

    db.commit()
    return BulkDeleteResponse(deleted=deleted)


@router.delete(
    "/{job_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_attachment(
    job_id: int,
    attachment_id: int,
    payload: PasswordConfirmRequest,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    admin: User = Depends(require_admin),
) -> Response:
    _require_admin_password(payload.password, admin)
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

    # Walk up from the deleted file's parent toward job_dir, rmdir-ing
    # any directory that just emptied out. Stops at job_dir itself,
    # which gets the same treatment as the final step. rmdir refuses
    # non-empty dirs, so other siblings keep their parents alive on
    # purpose.
    current = file_path.parent
    while current.is_relative_to(job_dir) or current == job_dir:
        try:
            current.rmdir()
        except OSError:
            break
        if current == job_dir:
            break
        current = current.parent

    db.delete(attachment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
