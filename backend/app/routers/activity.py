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
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> ActivityResponse:
    # Pull each table's own top N independently — the global top N can
    # never include rows past either table's own top N (within a table
    # the rows are already timestamp-sorted), so a limited Python merge
    # is exact without having to scan the whole feed.
    members = (
        db.query(Member).order_by(Member.joined_at.desc()).limit(limit).all()
    )
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(limit).all()

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
    )[:limit]
    return ActivityResponse(items=merged)
