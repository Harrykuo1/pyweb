from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import (
    require_admin_password,
    require_completed_member,
    require_posting_member,
)
from app.core.member_display import member_display_map
from app.database import get_db
from app.models import Job, JobComment, Member, PostStatus, User, UserRole
from app.schemas import (
    CommentCreate,
    CommentResponse,
    CommentUpdate,
    PasswordConfirmRequest,
)

router = APIRouter(prefix="/api/jobs", tags=["job_comments"])


def _visible_job_or_404(db: Session, job_id: int, user: User) -> Job:
    """The job, but 404 if it's not visible to this viewer — same rule as
    jobs.get_job: admins see everything, others only accepted posts plus the
    ones they are the subject of."""
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


def _comment_or_404(db: Session, job_id: int, comment_id: int) -> JobComment:
    comment = db.query(JobComment).filter_by(id=comment_id, job_id=job_id).one_or_none()
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到留言")
    return comment


def _to_response(
    comment: JobComment,
    *,
    is_admin: bool,
    viewer_user_id: int,
    author: dict | None,
) -> CommentResponse:
    is_author = (
        comment.author_user_id is not None and comment.author_user_id == viewer_user_id
    )
    author = author or {}
    return CommentResponse(
        id=comment.id,
        body=comment.body,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
        author_display_name=author.get("name"),
        author_member_id=author.get("member_id"),
        author_has_photo=author.get("has_photo", False),
        author_photo_updated_at=author.get("photo_updated_at"),
        author_user_id=comment.author_user_id if is_admin else None,
        can_edit=is_author,
        can_delete=is_admin or is_author,
    )


@router.get("/{job_id}/comments", response_model=list[CommentResponse])
def list_comments(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
) -> list[CommentResponse]:
    _visible_job_or_404(db, job_id, current_user)
    comments = (
        db.query(JobComment)
        .filter_by(job_id=job_id)
        .order_by(JobComment.id.asc())
        .all()
    )
    is_admin = current_user.role is UserRole.ADMIN
    authors = member_display_map(db, [c.author_user_id for c in comments])
    return [
        _to_response(
            c,
            is_admin=is_admin,
            viewer_user_id=current_user.id,
            author=authors.get(c.author_user_id),
        )
        for c in comments
    ]


@router.post(
    "/{job_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    job_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> CommentResponse:
    _visible_job_or_404(db, job_id, current_user)
    comment = JobComment(
        job_id=job_id,
        author_user_id=current_user.id,
        body=payload.body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    authors = member_display_map(db, [comment.author_user_id])
    return _to_response(
        comment,
        is_admin=current_user.role is UserRole.ADMIN,
        viewer_user_id=current_user.id,
        author=authors.get(comment.author_user_id),
    )


@router.put("/{job_id}/comments/{comment_id}", response_model=CommentResponse)
def update_comment(
    job_id: int,
    comment_id: int,
    payload: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> CommentResponse:
    comment = _comment_or_404(db, job_id, comment_id)
    if comment.author_user_id is None or comment.author_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="不能編輯別人的留言"
        )
    comment.body = payload.body
    comment.edited_at = datetime.now(UTC)
    db.commit()
    db.refresh(comment)
    authors = member_display_map(db, [comment.author_user_id])
    return _to_response(
        comment,
        is_admin=current_user.role is UserRole.ADMIN,
        viewer_user_id=current_user.id,
        author=authors.get(comment.author_user_id),
    )


@router.delete(
    "/{job_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_comment(
    job_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
    payload: PasswordConfirmRequest | None = None,
) -> None:
    comment = _comment_or_404(db, job_id, comment_id)
    is_admin = current_user.role is UserRole.ADMIN
    is_author = (
        comment.author_user_id is not None and comment.author_user_id == current_user.id
    )
    if not is_admin and not is_author:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="不能刪除別人的留言"
        )
    if is_admin and not is_author:
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password is required",
            )
        require_admin_password(db, payload.password)
    db.delete(comment)
    db.commit()
