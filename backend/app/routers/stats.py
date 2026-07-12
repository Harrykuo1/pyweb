from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.deps import require_completed_member
from app.database import get_db
from app.models import Event, Job, Member, PostStatus, User, UserRole
from app.schemas.stats import StatsResponse

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
) -> StatsResponse:
    is_admin = current_user.role is UserRole.ADMIN

    members_q = db.query(func.count(Member.id))
    jobs_q = db.query(func.count(Job.id))
    events_q = db.query(func.count(Event.id))
    companies_q = db.query(func.count(func.distinct(Job.company)))
    years_q = db.query(func.min(Job.job_year), func.max(Job.job_year))

    if not is_admin:
        # Public totals: count only what a non-admin can actually see, so the
        # numbers never betray the existence of hidden (pending/rejected)
        # posts or suspended members (which the list endpoints already hide).
        members_q = members_q.outerjoin(User, User.id == Member.user_id).filter(
            or_(Member.user_id.is_(None), User.is_active.is_(True))
        )
        accepted_job = Job.status == PostStatus.ACCEPTED
        jobs_q = jobs_q.filter(accepted_job)
        companies_q = companies_q.filter(accepted_job)
        years_q = years_q.filter(accepted_job)
        events_q = events_q.filter(Event.status == PostStatus.ACCEPTED)

    year_min, year_max = years_q.one()
    return StatsResponse(
        total_members=members_q.scalar() or 0,
        total_jobs=jobs_q.scalar() or 0,
        total_events=events_q.scalar() or 0,
        total_companies=companies_q.scalar() or 0,
        year_min=year_min,
        year_max=year_max,
    )
