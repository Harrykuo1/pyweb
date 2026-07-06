from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import require_completed_member
from app.database import get_db
from app.models import Event, Job, Member
from app.schemas.stats import StatsResponse

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    _: object = Depends(require_completed_member),
) -> StatsResponse:
    total_members = db.query(func.count(Member.id)).scalar() or 0
    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    total_events = db.query(func.count(Event.id)).scalar() or 0
    total_companies = db.query(func.count(func.distinct(Job.company))).scalar() or 0
    year_min, year_max = db.query(
        func.min(Job.job_year),
        func.max(Job.job_year),
    ).one()
    return StatsResponse(
        total_members=total_members,
        total_jobs=total_jobs,
        total_events=total_events,
        total_companies=total_companies,
        year_min=year_min,
        year_max=year_max,
    )
