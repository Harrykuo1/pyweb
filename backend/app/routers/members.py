from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

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

RESUME_PDF_MAX_BYTES = 10 * 1024 * 1024
RESUME_PDF_TYPE = "application/pdf"


def _get_member_or_404(db: Session, member_id: int) -> Member:
    member = db.query(Member).filter_by(id=member_id).one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return member


def _require_admin_password(payload: PasswordConfirmRequest, admin: User) -> None:
    """Re-authenticate the admin before a destructive action."""
    if not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
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
        joined_at=payload.joined_at or datetime.now(timezone.utc),
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
    _: object = Depends(get_current_user),
) -> Response:
    member = _get_member_or_404(db, member_id)
    if member.photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No photo")
    return Response(
        content=member.photo,
        media_type=member.photo_content_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=60"},
    )


@router.post("/{member_id}/photo", response_model=MemberResponse)
async def upload_member_photo(
    member_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
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
    member.photo = data
    member.photo_content_type = file.content_type
    member.photo_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_member_photo(
    member_id: int,
    payload: PasswordConfirmRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    _require_admin_password(payload, admin)
    member = _get_member_or_404(db, member_id)
    member.photo = None
    member.photo_content_type = None
    member.photo_updated_at = None
    db.commit()


# ---------- resume pdf ----------

@router.get("/{member_id}/resume.pdf")
async def get_member_resume_pdf(
    member_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> Response:
    member = _get_member_or_404(db, member_id)
    if member.resume_pdf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No resume pdf")
    return Response(
        content=member.resume_pdf,
        media_type=RESUME_PDF_TYPE,
        headers={
            "Cache-Control": "private, max-age=60",
            "Content-Disposition": f'inline; filename="member-{member_id}-resume.pdf"',
        },
    )


@router.post("/{member_id}/resume.pdf", response_model=MemberResponse)
async def upload_member_resume_pdf(
    member_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
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
    member.resume_pdf = data
    member.resume_pdf_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}/resume.pdf", status_code=status.HTTP_204_NO_CONTENT)
def delete_member_resume_pdf(
    member_id: int,
    payload: PasswordConfirmRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    _require_admin_password(payload, admin)
    member = _get_member_or_404(db, member_id)
    member.resume_pdf = None
    member.resume_pdf_updated_at = None
    db.commit()
