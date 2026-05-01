from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.search_query import build_ilike_filter, parse as parse_search_query
from app.core.security import verify_password
from app.database import get_db
from app.models import Job, JobKind, User
from app.schemas import (
    JobCreate,
    JobResponse,
    JobUpdate,
    ListResponse,
    PasswordConfirmRequest,
)
from app.schemas.job import JobKindLiteral

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

SortField = Literal["created_at", "job_year", "company", "real_name", "kind"]
SortOrder = Literal["asc", "desc"]

_SORT_COLUMNS = {
    "created_at": Job.created_at,
    "job_year": Job.job_year,
    "company": Job.company,
    "real_name": Job.real_name,
}

# Internship sorts before fulltime in ascending order — matches the app's
# original framing where internship records came first.
_KIND_PRIORITY = case(
    (Job.kind == JobKind.INTERNSHIP, 0),
    else_=1,
)

COMPANIES_AUTOCOMPLETE_LIMIT = 20
CATEGORIES_AUTOCOMPLETE_LIMIT = 20


def _get_or_404(db: Session, job_id: int) -> Job:
    obj = db.query(Job).filter_by(id=job_id).one_or_none()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return obj


def _require_admin_password(payload: PasswordConfirmRequest, admin: User) -> None:
    if not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password is incorrect",
        )


@router.get("", response_model=ListResponse[JobResponse])
def list_jobs(
    sort: SortField = "created_at",
    order: SortOrder = "desc",
    year: int | None = None,
    # Repeatable: ?company=A&company=B → OR-matched against Job.company.
    # Capped server-side so a malicious caller can't blow up the IN clause.
    company: list[str] = Query(default_factory=list, max_length=10),
    category: list[str] = Query(default_factory=list, max_length=10),
    kind: JobKindLiteral | None = None,
    q: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> ListResponse[JobResponse]:
    query = db.query(Job)

    if year is not None:
        query = query.filter(Job.job_year == year)
    if company:
        query = query.filter(Job.company.in_(company))
    if category:
        query = query.filter(Job.category.in_(category))
    if kind is not None:
        query = query.filter(Job.kind == kind)
    if q:
        # Company is filtered separately via the multi-select tag picker,
        # so keep q focused on free-form text fields. Supports boolean
        # syntax (AND / OR / NOT / -prefix / "phrase") via search_query.
        expr = build_ilike_filter(
            parse_search_query(q),
            [Job.real_name, Job.experience_md],
        )
        if expr is not None:
            query = query.filter(expr)

    if sort == "kind":
        primary = _KIND_PRIORITY.asc() if order == "asc" else _KIND_PRIORITY.desc()
        # Group same-kind rows together and order within by recency.
        order_by = [primary, Job.created_at.desc()]
    elif sort == "real_name":
        column = _SORT_COLUMNS[sort]
        primary = column.asc() if order == "asc" else column.desc()
        # Anonymous rows always sink to the bottom regardless of asc/desc.
        order_by = [Job.real_name.is_(None), primary, Job.created_at.desc()]
    elif sort == "created_at":
        column = _SORT_COLUMNS[sort]
        order_by = [column.asc() if order == "asc" else column.desc()]
    elif sort == "job_year":
        # Year+month chronological — month is the secondary key so a
        # 2024-12 record sits ahead of 2024-01 in descending order.
        year_col = Job.job_year.asc() if order == "asc" else Job.job_year.desc()
        month_col = Job.job_month.asc() if order == "asc" else Job.job_month.desc()
        order_by = [year_col, month_col, Job.created_at.desc()]
    else:
        column = _SORT_COLUMNS[sort]
        primary = column.asc() if order == "asc" else column.desc()
        order_by = [primary, Job.created_at.desc()]

    items = query.order_by(*order_by).all()
    return ListResponse[JobResponse](
        items=[JobResponse.model_validate(i) for i in items],
        total=len(items),
    )


@router.get("/companies", response_model=list[str])
def list_companies(
    prefix: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> list[str]:
    query = db.query(Job.company).distinct()
    if prefix:
        query = query.filter(Job.company.ilike(f"{prefix}%"))
    rows = (
        query.order_by(Job.company)
        .limit(COMPANIES_AUTOCOMPLETE_LIMIT)
        .all()
    )
    return [row[0] for row in rows]


@router.get("/categories", response_model=list[str])
def list_categories(
    prefix: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> list[str]:
    # Skip NULL rows so they don't surface as a phantom autocomplete option.
    query = db.query(Job.category).distinct().filter(Job.category.is_not(None))
    if prefix:
        query = query.filter(Job.category.ilike(f"{prefix}%"))
    rows = (
        query.order_by(Job.category)
        .limit(CATEGORIES_AUTOCOMPLETE_LIMIT)
        .all()
    )
    return [row[0] for row in rows]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> Job:
    return _get_or_404(db, job_id)


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Job:
    obj = Job(
        job_year=payload.job_year,
        job_month=payload.job_month,
        company=payload.company,
        category=payload.category,
        kind=JobKind(payload.kind),
        experience_md=payload.experience_md,
        real_name=payload.real_name,
        timeline_md=payload.timeline_md,
        # Pydantic gives us TimelineEvent instances containing date
        # objects; SQLAlchemy's JSON column needs plain dicts with
        # JSON-serialisable scalars, so use mode="json" to force the
        # date -> ISO string conversion at the boundary.
        timeline_events=(
            [e.model_dump(mode="json") for e in payload.timeline_events]
            if payload.timeline_events is not None
            else None
        ),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Job:
    obj = _get_or_404(db, job_id)
    # mode="json" so any nested date objects (timeline_events[].date)
    # arrive at the SQLAlchemy JSON column already serialised to ISO
    # strings — same boundary handling as create_job above.
    for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
        if field == "kind" and value is not None:
            value = JobKind(value)
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    payload: PasswordConfirmRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    _require_admin_password(payload, admin)
    obj = _get_or_404(db, job_id)
    db.delete(obj)
    db.commit()
