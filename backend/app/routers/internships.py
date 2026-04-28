from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.security import verify_password
from app.database import get_db
from app.models import Internship, JobKind, User
from app.schemas import (
    InternshipCreate,
    InternshipResponse,
    InternshipUpdate,
    ListResponse,
    PasswordConfirmRequest,
)
from app.schemas.internship import JobKindLiteral

router = APIRouter(prefix="/api/internships", tags=["internships"])

SortField = Literal["created_at", "job_year", "company", "real_name", "kind"]
SortOrder = Literal["asc", "desc"]

_SORT_COLUMNS = {
    "created_at": Internship.created_at,
    "job_year": Internship.job_year,
    "company": Internship.company,
    "real_name": Internship.real_name,
}

# Internship sorts before fulltime in ascending order — matches the app's
# original framing where internship records came first.
_KIND_PRIORITY = case(
    (Internship.kind == JobKind.INTERNSHIP, 0),
    else_=1,
)

COMPANIES_AUTOCOMPLETE_LIMIT = 20


def _get_or_404(db: Session, internship_id: int) -> Internship:
    obj = db.query(Internship).filter_by(id=internship_id).one_or_none()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Internship not found",
        )
    return obj


def _require_admin_password(payload: PasswordConfirmRequest, admin: User) -> None:
    if not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password is incorrect",
        )


@router.get("", response_model=ListResponse[InternshipResponse])
def list_internships(
    sort: SortField = "created_at",
    order: SortOrder = "desc",
    year: int | None = None,
    company: str | None = None,
    kind: JobKindLiteral | None = None,
    q: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> ListResponse[InternshipResponse]:
    query = db.query(Internship)

    if year is not None:
        query = query.filter(Internship.job_year == year)
    if company:
        query = query.filter(Internship.company == company)
    if kind is not None:
        query = query.filter(Internship.kind == kind)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                Internship.company.ilike(pattern),
                Internship.real_name.ilike(pattern),
                Internship.experience_md.ilike(pattern),
            )
        )

    if sort == "kind":
        primary = _KIND_PRIORITY.asc() if order == "asc" else _KIND_PRIORITY.desc()
        # Group same-kind rows together and order within by recency.
        order_by = [primary, Internship.created_at.desc()]
    elif sort == "real_name":
        column = _SORT_COLUMNS[sort]
        primary = column.asc() if order == "asc" else column.desc()
        # Anonymous rows always sink to the bottom regardless of asc/desc.
        order_by = [Internship.real_name.is_(None), primary, Internship.created_at.desc()]
    elif sort == "created_at":
        column = _SORT_COLUMNS[sort]
        order_by = [column.asc() if order == "asc" else column.desc()]
    else:
        column = _SORT_COLUMNS[sort]
        primary = column.asc() if order == "asc" else column.desc()
        order_by = [primary, Internship.created_at.desc()]

    items = query.order_by(*order_by).all()
    return ListResponse[InternshipResponse](
        items=[InternshipResponse.model_validate(i) for i in items],
        total=len(items),
    )


@router.get("/companies", response_model=list[str])
def list_companies(
    prefix: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> list[str]:
    query = db.query(Internship.company).distinct()
    if prefix:
        query = query.filter(Internship.company.ilike(f"{prefix}%"))
    rows = (
        query.order_by(Internship.company)
        .limit(COMPANIES_AUTOCOMPLETE_LIMIT)
        .all()
    )
    return [row[0] for row in rows]


@router.get("/{internship_id}", response_model=InternshipResponse)
def get_internship(
    internship_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> Internship:
    return _get_or_404(db, internship_id)


@router.post(
    "",
    response_model=InternshipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_internship(
    payload: InternshipCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Internship:
    obj = Internship(
        job_year=payload.job_year,
        company=payload.company,
        kind=JobKind(payload.kind),
        experience_md=payload.experience_md,
        real_name=payload.real_name,
        timeline_md=payload.timeline_md,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{internship_id}", response_model=InternshipResponse)
def update_internship(
    internship_id: int,
    payload: InternshipUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Internship:
    obj = _get_or_404(db, internship_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "kind" and value is not None:
            value = JobKind(value)
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{internship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_internship(
    internship_id: int,
    payload: PasswordConfirmRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    _require_admin_password(payload, admin)
    obj = _get_or_404(db, internship_id)
    db.delete(obj)
    db.commit()
