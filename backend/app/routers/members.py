from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.core.security import verify_password
from app.database import get_db
from app.models import Member, User
from app.schemas import (
    MemberCreate,
    MemberResponse,
    MemberUpdate,
    PasswordConfirmRequest,
)

router = APIRouter(prefix="/api/members", tags=["members"])

PHOTO_MAX_BYTES = 5 * 1024 * 1024
ALLOWED_PHOTO_TYPES = {"image/png", "image/jpeg", "image/webp"}
# Mirror the mapping in migration 0013 so a freshly-uploaded photo
# lands on the same canonical extension the backfill would have picked.
PHOTO_MIME_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

RESUME_PDF_MAX_BYTES = 10 * 1024 * 1024
RESUME_PDF_TYPE = "application/pdf"


def get_uploads_root() -> Path:
    """FastAPI dependency that resolves the configured uploads root.

    Mirrors the job_attachments router's pattern so tests can swap in
    a tmp_path via ``app.dependency_overrides`` without monkey-patching
    the settings module."""
    return Path(settings.uploads_dir)


def _try_remove_member_dir(uploads_root: Path, member_id: int) -> None:
    """rmdir the per-member directory if it just emptied out. Mirrors
    job_attachments' bottom-up cleanup: the directory only ever holds
    photo.<ext> and resume.pdf, so once both are gone there's nothing
    left to reap."""
    member_dir = uploads_root / "members" / str(member_id)
    try:
        member_dir.rmdir()
    except OSError:
        pass


def _get_member_or_404(db: Session, member_id: int) -> Member:
    member = db.query(Member).filter_by(id=member_id).one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )
    return member


def _require_admin_password(payload: PasswordConfirmRequest, admin: User) -> None:
    """Re-authenticate the admin before a destructive action.

    Returns 422 (not 401) on mismatch so the global axios auth-interceptor
    doesn't treat a typo'd confirmation password as an expired session and
    bounce the user back to /login. Session is still valid here — only
    the body-supplied password is wrong, which is a request-validation
    failure, not an auth failure.
    """
    if not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password is incorrect",
        )


@router.get("", response_model=list[MemberResponse])
def list_members(
    order: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> list[Member]:
    column = Member.joined_at.asc() if order == "asc" else Member.joined_at.desc()
    return db.query(Member).order_by(column).all()


@router.get("/{member_id}", response_model=MemberResponse)
def get_member(
    member_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> Member:
    return _get_member_or_404(db, member_id)


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Member:
    member = Member(
        graduation_year=payload.graduation_year,
        real_name=payload.real_name,
        institution=payload.institution,
        position=payload.position,
        resume_md=payload.resume_md,
        joined_at=payload.joined_at or datetime.now(UTC),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/{member_id}", response_model=MemberResponse)
def update_member(
    member_id: int,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Member:
    member = _get_member_or_404(db, member_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(
    member_id: int,
    payload: PasswordConfirmRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    _require_admin_password(payload, admin)
    member = _get_member_or_404(db, member_id)
    db.delete(member)
    db.commit()


# ---------- photo ----------


@router.get("/{member_id}/photo")
async def get_member_photo(
    member_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    _: object = Depends(get_current_user),
) -> Response:
    member = _get_member_or_404(db, member_id)
    if not member.photo_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No photo")
    file_path = uploads_root / member.photo_path
    if not file_path.exists():
        # DB points at a file that vanished out-of-band — surface a
        # clean 404 rather than letting FileResponse 500 on the missing
        # stat. Matches the job_attachments download handler.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Photo file missing"
        )
    return FileResponse(
        file_path,
        media_type=member.photo_content_type or "application/octet-stream",
        headers={
            # The URL is content-addressed via ?v=<photo_updated_at>, so
            # a given URL always points at the same bytes. Tell the
            # browser to cache forever and skip even conditional
            # revalidation — admin replacing the photo bumps
            # photo_updated_at, which changes the URL and naturally
            # produces a cache miss.
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{member_id}/photo", response_model=MemberResponse)
async def upload_member_photo(
    member_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    _: object = Depends(require_admin),
) -> Member:
    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Photo must be one of: {sorted(ALLOWED_PHOTO_TYPES)}",
        )
    data = await file.read()
    if len(data) > PHOTO_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Photo must be at most {PHOTO_MAX_BYTES} bytes",
        )

    member = _get_member_or_404(db, member_id)
    ext = PHOTO_MIME_TO_EXT[file.content_type]
    new_relpath = f"members/{member_id}/photo{ext}"

    # If the prior photo lived under a different extension (png -> jpg
    # swap), remove the stale file so the per-member directory doesn't
    # accumulate orphan variants. Same-extension overwrites just
    # truncate the existing file via write_bytes below.
    if member.photo_path and member.photo_path != new_relpath:
        old_path = uploads_root / member.photo_path
        if old_path.exists():
            old_path.unlink()

    new_path = uploads_root / new_relpath
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_bytes(data)

    member.photo_path = new_relpath
    member.photo_content_type = file.content_type
    member.photo_updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_member_photo(
    member_id: int,
    payload: PasswordConfirmRequest,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    admin: User = Depends(require_admin),
) -> None:
    _require_admin_password(payload, admin)
    member = _get_member_or_404(db, member_id)
    if member.photo_path:
        file_path = uploads_root / member.photo_path
        if file_path.exists():
            file_path.unlink()
    member.photo_path = None
    member.photo_content_type = None
    member.photo_updated_at = None
    db.commit()
    _try_remove_member_dir(uploads_root, member_id)


# ---------- resume pdf ----------


@router.get("/{member_id}/resume.pdf")
async def get_member_resume_pdf(
    member_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    _: object = Depends(get_current_user),
) -> Response:
    member = _get_member_or_404(db, member_id)
    if not member.resume_pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No resume pdf"
        )
    file_path = uploads_root / member.resume_pdf_path
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume file missing"
        )
    return FileResponse(
        file_path,
        media_type=RESUME_PDF_TYPE,
        headers={
            # URL is content-addressed via ?v=<resume_pdf_updated_at>;
            # see the photo endpoint above for the rationale.
            "Cache-Control": "private, max-age=31536000, immutable",
            "Content-Disposition": f'inline; filename="member-{member_id}-resume.pdf"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{member_id}/resume.pdf", response_model=MemberResponse)
async def upload_member_resume_pdf(
    member_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    _: object = Depends(require_admin),
) -> Member:
    if file.content_type != RESUME_PDF_TYPE:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Resume must be {RESUME_PDF_TYPE}",
        )
    data = await file.read()
    if len(data) > RESUME_PDF_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Resume must be at most {RESUME_PDF_MAX_BYTES} bytes",
        )

    member = _get_member_or_404(db, member_id)
    relpath = f"members/{member_id}/resume.pdf"
    target = uploads_root / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    member.resume_pdf_path = relpath
    member.resume_pdf_updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}/resume.pdf", status_code=status.HTTP_204_NO_CONTENT)
def delete_member_resume_pdf(
    member_id: int,
    payload: PasswordConfirmRequest,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    admin: User = Depends(require_admin),
) -> None:
    _require_admin_password(payload, admin)
    member = _get_member_or_404(db, member_id)
    if member.resume_pdf_path:
        file_path = uploads_root / member.resume_pdf_path
        if file_path.exists():
            file_path.unlink()
    member.resume_pdf_path = None
    member.resume_pdf_updated_at = None
    db.commit()
    _try_remove_member_dir(uploads_root, member_id)
