from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import require_completed_member, require_posting_member
from app.core.member_display import member_display_map
from app.database import get_db
from app.models import Job, JobLike, Member, PostStatus, User, UserRole
from app.schemas import LikerResponse, LikeStatusResponse

router = APIRouter(prefix="/api/jobs", tags=["job_likes"])


def _visible_job_or_404(db: Session, job_id: int, user: User) -> Job:
    # Mirrors job_comments._visible_job_or_404.
    job = db.query(Job).filter_by(id=job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到貼文")
    is_admin = user.role is UserRole.ADMIN
    member_row = db.query(Member.id).filter_by(user_id=user.id).first()
    viewer_member_id = member_row[0] if member_row is not None else None
    is_owner = (
        job.subject_member_id is not None and job.subject_member_id == viewer_member_id
    )
    if not is_admin and job.status is not PostStatus.ACCEPTED and not is_owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到貼文")
    return job


def _like_count(db: Session, job_id: int) -> int:
    return db.query(func.count(JobLike.id)).filter_by(job_id=job_id).scalar() or 0


@router.post("/{job_id}/like", response_model=LikeStatusResponse)
def like_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> LikeStatusResponse:
    _visible_job_or_404(db, job_id, current_user)
    existing = (
        db.query(JobLike)
        .filter_by(job_id=job_id, user_id=current_user.id)
        .one_or_none()
    )
    if existing is None:
        db.add(JobLike(job_id=job_id, user_id=current_user.id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return LikeStatusResponse(like_count=_like_count(db, job_id), liked=True)


@router.delete("/{job_id}/like", response_model=LikeStatusResponse)
def unlike_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> LikeStatusResponse:
    _visible_job_or_404(db, job_id, current_user)
    existing = (
        db.query(JobLike)
        .filter_by(job_id=job_id, user_id=current_user.id)
        .one_or_none()
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
    return LikeStatusResponse(like_count=_like_count(db, job_id), liked=False)


@router.get("/{job_id}/likes", response_model=list[LikerResponse])
def list_likers(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
) -> list[LikerResponse]:
    _visible_job_or_404(db, job_id, current_user)
    user_ids = [
        uid
        for (uid,) in db.query(JobLike.user_id)
        .filter_by(job_id=job_id)
        .order_by(JobLike.id.desc())
    ]
    infos = member_display_map(db, user_ids)
    out: list[LikerResponse] = []
    for uid in user_ids:
        info = infos.get(uid, {})
        out.append(
            LikerResponse(
                user_id=uid,
                display_name=info.get("name"),
                member_id=info.get("member_id"),
                has_photo=info.get("has_photo", False),
                photo_updated_at=info.get("photo_updated_at"),
            )
        )
    return out
