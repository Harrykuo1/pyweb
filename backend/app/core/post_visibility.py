"""Who is allowed to see a given event or job.

Events and jobs answer "is this mine?" differently — an event by its author
user, a job by its subject member — but the rule around that is the same:
admins see everything, everyone else sees accepted posts plus their own.

This lives here because the comment and like routers each grew their own copy
of it. Four copies of an access rule is four places to keep in step, and the
failure mode of missing one is silent: the reader gets a post they shouldn't
see, with no error and nothing in a log.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Event, Job, Member, PostStatus, User, UserRole


def resolve_viewer_member_id(db: Session, user: User) -> int | None:
    """The member profile behind this account, if it has one."""
    row = db.query(Member.id).filter_by(user_id=user.id).first()
    return row[0] if row is not None else None


def visible_event_or_404(db: Session, event_id: int, user: User) -> Event:
    event = db.query(Event).filter_by(id=event_id).one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到活動")
    is_admin = user.role is UserRole.ADMIN
    is_owner = event.author_user_id is not None and event.author_user_id == user.id
    # 404 rather than 403: a pending post's existence is itself private.
    if not is_admin and event.status is not PostStatus.ACCEPTED and not is_owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到活動")
    return event


def visible_job_or_404(db: Session, job_id: int, user: User) -> Job:
    job = db.query(Job).filter_by(id=job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到貼文")
    is_admin = user.role is UserRole.ADMIN
    is_owner = (
        job.subject_member_id is not None
        and job.subject_member_id == resolve_viewer_member_id(db, user)
    )
    if not is_admin and job.status is not PostStatus.ACCEPTED and not is_owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到貼文")
    return job
