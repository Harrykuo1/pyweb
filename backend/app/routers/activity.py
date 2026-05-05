from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import Job, Member
from app.schemas.activity import (
    ActivityResponse,
    JobCreatedActivity,
    MemberJoinedActivity,
)

router = APIRouter(prefix="/api/activity", tags=["activity"])

ACTIVITY_LIMIT_DEFAULT = 10
ACTIVITY_LIMIT_MAX = 50


@router.get("", response_model=ActivityResponse)
def list_activity(
    limit: int = Query(default=ACTIVITY_LIMIT_DEFAULT, ge=1, le=ACTIVITY_LIMIT_MAX),
    before: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> ActivityResponse:
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
    members_q = db.query(Member).order_by(Member.joined_at.desc())
    jobs_q = db.query(Job).order_by(Job.created_at.desc())
    if before is not None:
        members_q = members_q.filter(Member.joined_at < before)
        jobs_q = jobs_q.filter(Job.created_at < before)

    peek = limit + 1
    members = members_q.limit(peek).all()
    jobs = jobs_q.limit(peek).all()

    member_items: list[MemberJoinedActivity | JobCreatedActivity] = [
        MemberJoinedActivity(
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
    job_items: list[MemberJoinedActivity | JobCreatedActivity] = [
        JobCreatedActivity(
            timestamp=j.created_at,
            job_id=j.id,
            company=j.company,
            kind=j.kind.value,
            category=j.category,
            real_name=j.real_name,
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
    return ActivityResponse(items=merged[:limit], has_more=has_more)
