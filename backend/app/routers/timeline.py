from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_completed_member
from app.core.job_serialize import job_display_name
from app.database import get_db
from app.models import Job, Member, PostStatus, User, UserRole
from app.schemas.timeline import (
    JobCreatedItem,
    MemberJoinedItem,
    TimelineResponse,
)

router = APIRouter(prefix="/api/timeline", tags=["timeline"])

TIMELINE_LIMIT_DEFAULT = 10
TIMELINE_LIMIT_MAX = 50


@router.get("", response_model=TimelineResponse)
def list_timeline(
    limit: int = Query(default=TIMELINE_LIMIT_DEFAULT, ge=1, le=TIMELINE_LIMIT_MAX),
    before: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
) -> TimelineResponse:
    # Cursor pagination: when `before` is supplied, return only rows
    # strictly older than that timestamp. Frontend passes the timestamp
    # of the last item it received to walk the feed backwards as the
    # user scrolls.
    #
    # Pull `limit + 1` from each table so we can peek one past the
    # requested page size — if the merged top (limit + 1) has more than
    # `limit` rows, we know at least one older row exists and set
    # has_more=True. This avoids a separate count query.
    #
    # The merge correctness argument is unchanged from the original
    # endpoint: within a single table rows are timestamp-sorted, so the
    # global top N (older than `before`) cannot include rows past either
    # table's own top N.
    is_admin = current_user.role is UserRole.ADMIN
    vm = db.query(Member.id).filter_by(user_id=current_user.id).first()
    viewer_member_id = vm[0] if vm is not None else None

    members_q = db.query(Member).order_by(Member.joined_at.desc())
    jobs_q = db.query(Job).order_by(Job.created_at.desc())
    # Non-admins never see unaccepted posts in the feed (their own aside).
    if not is_admin:
        own = (
            Job.subject_member_id == viewer_member_id
            if viewer_member_id is not None
            else False
        )
        jobs_q = jobs_q.filter((Job.status == PostStatus.ACCEPTED) | own)
    if before is not None:
        members_q = members_q.filter(Member.joined_at < before)
        jobs_q = jobs_q.filter(Job.created_at < before)

    peek = limit + 1
    members = members_q.limit(peek).all()
    jobs = jobs_q.limit(peek).all()

    member_items: list[MemberJoinedItem | JobCreatedItem] = [
        MemberJoinedItem(
            timestamp=m.joined_at,
            member_id=m.id,
            real_name=m.real_name,
            institution=m.institution,
            position=m.position,
            has_photo=m.has_photo,
            photo_updated_at=m.photo_updated_at,
        )
        for m in members
    ]
    subj_names = dict(
        db.query(Member.id, Member.real_name)
        .filter(
            Member.id.in_([j.subject_member_id for j in jobs if j.subject_member_id])
        )
        .all()
    )
    job_items: list[MemberJoinedItem | JobCreatedItem] = [
        JobCreatedItem(
            timestamp=j.created_at,
            job_id=j.id,
            company=j.company,
            kind=j.kind.value,
            category=j.category,
            # §8: anonymous posts expose no author name to non-admins.
            real_name=job_display_name(
                j, is_admin=is_admin, subject_name=subj_names.get(j.subject_member_id)
            ),
            job_year=j.job_year,
            job_month=j.job_month,
        )
        for j in jobs
    ]

    merged = sorted(
        member_items + job_items,
        key=lambda x: x.timestamp,
        reverse=True,
    )[:peek]
    has_more = len(merged) > limit
    return TimelineResponse(items=merged[:limit], has_more=has_more)
