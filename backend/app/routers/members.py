import shutil
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
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import (
    require_admin,
    require_admin_password,
    require_completed_member,
    require_member,
)
from app.core.discord_link import normalize_discord_handle
from app.database import get_db
from app.models import Job, Member, User, UserRole
from app.schemas import (
    MemberCreate,
    MemberResponse,
    MemberSelfCreate,
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


def _owned_member_or_403(db: Session, member_id: int, user: User) -> Member:
    """Fetch the member, allowing admins or the member's own account through."""
    member = _get_member_or_404(db, member_id)
    if user.role is UserRole.ADMIN:
        return member
    if member.user_id is not None and member.user_id == user.id:
        return member
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Not your profile"
    )


def _member_response(member: Member, user: User | None) -> MemberResponse:
    """Fold the linked account's claim/suspend state into the member payload.

    Kept as a plain builder (not an ORM property) so the list endpoint can
    feed it rows from a single LEFT JOIN and avoid an N+1 on the account.
    """
    resp = MemberResponse.model_validate(member)
    if user is None:
        resp.account_status = "legacy"
        return resp
    resp.account_id = user.id
    resp.is_active = user.is_active
    # A pending account has no discord_username yet (only claimed accounts do);
    # surface pending_discord_username so the edit dialog can prefill and edits
    # of unrelated fields don't round-trip an empty handle that wipes it.
    resp.account_discord_username = (
        user.discord_username or user.pending_discord_username
    )
    if user.discord_id is None:
        resp.account_status = "pending"
    elif not user.is_active:
        resp.account_status = "suspended"
    else:
        resp.account_status = "claimed"
    return resp


def _is_member_visible(db: Session, member: Member, viewer: User) -> bool:
    """Suspended members (linked account is_active=False) are hidden from
    everyone except a real admin."""
    if viewer.role is UserRole.ADMIN:
        return True
    if member.user_id is None:
        return True
    active = db.query(User.is_active).filter_by(id=member.user_id).scalar()
    return active is not False  # None (no account) or active -> visible


@router.get("", response_model=list[MemberResponse])
def list_members(
    order: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db),
    viewer: User = Depends(require_completed_member),
) -> list[MemberResponse]:
    column = Member.joined_at.asc() if order == "asc" else Member.joined_at.desc()
    query = db.query(Member, User).outerjoin(User, User.id == Member.user_id)
    if viewer.role is not UserRole.ADMIN:
        # Hide suspended members: keep legacy rows (no account) and active accounts.
        query = query.filter(or_(Member.user_id.is_(None), User.is_active.is_(True)))
    rows = query.order_by(column).all()
    return [_member_response(m, u) for (m, u) in rows]


@router.get("/{member_id}", response_model=MemberResponse)
def get_member(
    member_id: int,
    db: Session = Depends(get_db),
    viewer: User = Depends(require_completed_member),
) -> MemberResponse:
    member = _get_member_or_404(db, member_id)
    if not _is_member_visible(db, member, viewer):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )
    user = (
        db.query(User).filter_by(id=member.user_id).one_or_none()
        if member.user_id is not None
        else None
    )
    return _member_response(member, user)


@router.post("/me", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_my_member_profile(
    payload: MemberSelfCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_member),
) -> Member:
    existing = db.query(Member).filter_by(user_id=current_user.id).one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account already has a member profile",
        )
    member = Member(
        user_id=current_user.id,
        graduation_year=payload.graduation_year,
        real_name=payload.real_name,
        institution=payload.institution,
        position=payload.position,
        resume_md=payload.resume_md,
        joined_at=datetime.now(UTC),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Member:
    handle = normalize_discord_handle(payload.discord_username)
    # Guard against a duplicate record for someone already registered: if the
    # handle already belongs to a linked account, the person is in the system
    # (via login or invite) and shouldn't be pre-created again.
    if handle is not None:
        claimed = (
            db.query(User.id)
            .filter(
                User.discord_id.isnot(None),
                func.lower(User.discord_username) == handle.lower(),
            )
            .first()
        )
        if claimed is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A registered account already uses this Discord username",
            )
    member = Member(
        graduation_year=payload.graduation_year,
        real_name=payload.real_name,
        institution=payload.institution,
        position=payload.position,
        resume_md=payload.resume_md,
        joined_at=payload.joined_at or datetime.now(UTC),
    )
    # Provision a role=MEMBER login account so the record isn't an orphan:
    # the admin-entered handle is parked in pending_discord_username, exactly
    # mirroring the migration backfill, so the first-login bridge auto-binds
    # (or queues) the account on the member's first Discord OAuth login.
    account = User(role=UserRole.MEMBER, pending_discord_username=handle)
    db.add(account)
    db.flush()
    member.user_id = account.id
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/{member_id}", response_model=MemberResponse)
def update_member(
    member_id: int,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_member),
) -> Member:
    member = _owned_member_or_403(db, member_id, current_user)
    data = payload.model_dump(exclude_unset=True)
    handle = data.pop("discord_username", None)  # not a Member column
    if current_user.role is not UserRole.ADMIN:
        data.pop("joined_at", None)  # members can't backdate their own join
    for field, value in data.items():
        setattr(member, field, value)
    # Admin may fix the pending handle of an UNCLAIMED linked account. A claimed
    # account (discord_id set) is left untouched — its identity is already bound.
    if (
        "discord_username" in payload.model_fields_set
        and current_user.role is UserRole.ADMIN
        and member.user_id is not None
    ):
        account = db.query(User).filter_by(id=member.user_id).one()
        if account.discord_id is None:
            account.pending_discord_username = normalize_discord_handle(handle)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(
    member_id: int,
    payload: PasswordConfirmRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    uploads_root: Path = Depends(get_uploads_root),
) -> None:
    require_admin_password(db, payload.password)
    member = _get_member_or_404(db, member_id)
    linked_user = (
        db.query(User).filter_by(id=member.user_id).one_or_none()
        if member.user_id is not None
        else None
    )
    # A claimed account (person has logged in via Discord) owns content through
    # author FKs and is their identity anchor for rejoining — never hard delete
    # it. Admin should suspend it instead (Settings -> 成員角色).
    if linked_user is not None and linked_user.discord_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This member has an active account; suspend it instead",
        )
    # A member still referenced by job records is content-bearing history —
    # deleting it would orphan those posts (or 500 on the FK). Preserve it,
    # same philosophy as the claimed-account guard above.
    referenced = db.query(Job.id).filter_by(subject_member_id=member_id).first()
    if referenced is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This member is referenced by job records and cannot be deleted",
        )
    # Unclaimed (pre-provisioned, never logged in) or legacy row: safe to remove
    # outright — no content, no other FK references. Delete the member first
    # (it holds the FK to users), then its unclaimed account if present.
    db.delete(member)
    if linked_user is not None:
        db.delete(linked_user)
    db.commit()
    shutil.rmtree(uploads_root / "members" / str(member_id), ignore_errors=True)


# ---------- photo ----------


@router.get("/{member_id}/photo")
async def get_member_photo(
    member_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    viewer: User = Depends(require_completed_member),
) -> Response:
    member = _get_member_or_404(db, member_id)
    if not _is_member_visible(db, member, viewer):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )
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
    current_user: User = Depends(require_member),
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

    member = _owned_member_or_403(db, member_id, current_user)
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
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    current_user: User = Depends(require_member),
    payload: PasswordConfirmRequest | None = None,
) -> None:
    member = _owned_member_or_403(db, member_id, current_user)
    if current_user.role is UserRole.ADMIN:
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password is required",
            )
        require_admin_password(db, payload.password)
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
    viewer: User = Depends(require_completed_member),
) -> Response:
    member = _get_member_or_404(db, member_id)
    if not _is_member_visible(db, member, viewer):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )
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
    current_user: User = Depends(require_member),
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

    member = _owned_member_or_403(db, member_id, current_user)
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
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    current_user: User = Depends(require_member),
    payload: PasswordConfirmRequest | None = None,
) -> None:
    member = _owned_member_or_403(db, member_id, current_user)
    if current_user.role is UserRole.ADMIN:
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password is required",
            )
        require_admin_password(db, payload.password)
    if member.resume_pdf_path:
        file_path = uploads_root / member.resume_pdf_path
        if file_path.exists():
            file_path.unlink()
    member.resume_pdf_path = None
    member.resume_pdf_updated_at = None
    db.commit()
    _try_remove_member_dir(uploads_root, member_id)
