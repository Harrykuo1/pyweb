import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.deps import (
    require_admin,
    require_admin_password,
    require_completed_member,
    require_posting_member,
)
from app.core.job_serialize import serialize_job
from app.core.search_query import build_ilike_filter
from app.core.search_query import parse as parse_search_query
from app.database import get_db
from app.models import (
    Job,
    JobAttachment,
    JobKind,
    JobLike,
    Member,
    PostStatus,
    User,
    UserRole,
)
from app.routers.job_attachments import get_uploads_root, job_uploads_dir
from app.schemas import (
    JobCreate,
    JobResponse,
    JobUpdate,
    ListResponse,
    PasswordConfirmRequest,
    RejectRequest,
)
from app.schemas.job import JobKindLiteral, PostStatusLiteral

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

SortField = Literal["created_at", "job_year", "company", "real_name", "kind", "likes"]
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


def _attachment_counts(db: Session, job_ids: list[int]) -> dict[int, int]:
    """Return {job_id: count} for the given jobs in a single query.
    Job IDs missing from the result map to 0 attachments — let the
    caller default via dict.get(..., 0)."""
    if not job_ids:
        return {}
    rows = (
        db.query(JobAttachment.job_id, func.count(JobAttachment.id))
        .filter(JobAttachment.job_id.in_(job_ids))
        .group_by(JobAttachment.job_id)
        .all()
    )
    return dict(rows)


def _viewer_member_id(db: Session, user: User) -> int | None:
    row = db.query(Member.id).filter_by(user_id=user.id).first()
    return row[0] if row is not None else None


def _subject_names(db: Session, member_ids: list[int | None]) -> dict[int, str]:
    ids = [m for m in member_ids if m is not None]
    if not ids:
        return {}
    rows = db.query(Member.id, Member.real_name).filter(Member.id.in_(ids)).all()
    return dict(rows)


def _likes_map(
    db: Session, job_ids: list[int], viewer_user_id: int
) -> dict[int, tuple[int, bool]]:
    """Return {job_id: (like_count, liked_by_viewer)} in two grouped queries."""
    if not job_ids:
        return {}
    counts = dict(
        db.query(JobLike.job_id, func.count(JobLike.id))
        .filter(JobLike.job_id.in_(job_ids))
        .group_by(JobLike.job_id)
        .all()
    )
    mine = {
        jid
        for (jid,) in db.query(JobLike.job_id).filter(
            JobLike.job_id.in_(job_ids),
            JobLike.user_id == viewer_user_id,
        )
    }
    return {jid: (counts.get(jid, 0), jid in mine) for jid in job_ids}


def _order_by(sort: str, order: str, is_admin: bool) -> list:
    if sort == "likes":
        like_count = (
            select(func.count(JobLike.id))
            .where(JobLike.job_id == Job.id)
            .correlate(Job)
            .scalar_subquery()
        )
        primary = like_count.asc() if order == "asc" else like_count.desc()
        return [primary, Job.created_at.desc()]
    if sort == "kind":
        primary = _KIND_PRIORITY.asc() if order == "asc" else _KIND_PRIORITY.desc()
        return [primary, Job.created_at.desc()]
    if sort == "real_name":
        # Public-safe name sort: anonymous rows expose no name to non-admins,
        # so they collapse to null (and sink) — never ordered by a hidden name.
        name_col = (
            Job.real_name
            if is_admin
            else case((Job.is_anonymous, None), else_=Job.real_name)
        )
        primary = name_col.asc() if order == "asc" else name_col.desc()
        return [name_col.is_(None), primary, Job.created_at.desc()]
    if sort == "created_at":
        col = Job.created_at
        return [col.asc() if order == "asc" else col.desc()]
    if sort == "job_year":
        year_col = Job.job_year.asc() if order == "asc" else Job.job_year.desc()
        month_col = Job.job_month.asc() if order == "asc" else Job.job_month.desc()
        return [year_col, month_col, Job.created_at.desc()]
    col = _SORT_COLUMNS[sort]
    primary = col.asc() if order == "asc" else col.desc()
    return [primary, Job.created_at.desc()]


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
    status_filter: PostStatusLiteral | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
) -> ListResponse[JobResponse]:
    is_admin = current_user.role is UserRole.ADMIN
    viewer_member_id = _viewer_member_id(db, current_user)

    query = db.query(Job)

    # Visibility: non-admins see accepted posts plus their own (by subject).
    if not is_admin:
        own = (
            Job.subject_member_id == viewer_member_id
            if viewer_member_id is not None
            else False
        )
        query = query.filter((Job.status == PostStatus.ACCEPTED) | own)
    if status_filter is not None:
        query = query.filter(Job.status == PostStatus(status_filter))

    if year is not None:
        query = query.filter(Job.job_year == year)
    if company:
        query = query.filter(Job.company.in_(company))
    if category:
        query = query.filter(Job.category.in_(category))
    if kind is not None:
        query = query.filter(Job.kind == kind)
    if q:
        # Non-admins must not be able to reverse-lookup an anonymous author
        # by searching a real name: restrict their text search to the
        # experience body. Admins may search real_name too.
        fields = [Job.experience_md]
        if is_admin:
            fields.append(Job.real_name)
        expr = build_ilike_filter(parse_search_query(q), fields)
        if expr is not None:
            query = query.filter(expr)

    items = query.order_by(*_order_by(sort, order, is_admin)).all()
    counts = _attachment_counts(db, [i.id for i in items])
    names = _subject_names(db, [i.subject_member_id for i in items])
    likes = _likes_map(db, [i.id for i in items], current_user.id)
    return ListResponse[JobResponse](
        items=[
            serialize_job(
                i,
                is_admin=is_admin,
                viewer_member_id=viewer_member_id,
                attachment_count=counts.get(i.id, 0),
                subject_name=names.get(i.subject_member_id),
                like_count=likes.get(i.id, (0, False))[0],
                liked_by_me=likes.get(i.id, (0, False))[1],
            )
            for i in items
        ],
        total=len(items),
    )


@router.get("/companies", response_model=list[str])
def list_companies(
    prefix: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    _: object = Depends(require_completed_member),
) -> list[str]:
    query = db.query(Job.company).distinct()
    if prefix:
        query = query.filter(Job.company.ilike(f"{prefix}%"))
    rows = query.order_by(Job.company).limit(COMPANIES_AUTOCOMPLETE_LIMIT).all()
    return [row[0] for row in rows]


@router.get("/categories", response_model=list[str])
def list_categories(
    prefix: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    _: object = Depends(require_completed_member),
) -> list[str]:
    # Skip NULL rows so they don't surface as a phantom autocomplete option.
    query = db.query(Job.category).distinct().filter(Job.category.is_not(None))
    if prefix:
        query = query.filter(Job.category.ilike(f"{prefix}%"))
    rows = query.order_by(Job.category).limit(CATEGORIES_AUTOCOMPLETE_LIMIT).all()
    return [row[0] for row in rows]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
) -> JobResponse:
    obj = _get_or_404(db, job_id)
    is_admin = current_user.role is UserRole.ADMIN
    viewer_member_id = _viewer_member_id(db, current_user)
    is_owner = (
        obj.subject_member_id is not None and obj.subject_member_id == viewer_member_id
    )
    # Don't let a non-admin fetch someone else's pending/rejected post by id —
    # 404 hides its very existence.
    if not is_admin and obj.status is not PostStatus.ACCEPTED and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    counts = _attachment_counts(db, [obj.id])
    names = _subject_names(db, [obj.subject_member_id])
    like_count, liked_by_me = _likes_map(db, [obj.id], current_user.id)[obj.id]
    return serialize_job(
        obj,
        is_admin=is_admin,
        viewer_member_id=viewer_member_id,
        attachment_count=counts.get(obj.id, 0),
        subject_name=names.get(obj.subject_member_id),
        like_count=like_count,
        liked_by_me=liked_by_me,
    )


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> JobResponse:
    is_admin = current_user.role is UserRole.ADMIN
    viewer_member_id = _viewer_member_id(db, current_user)

    if is_admin:
        # Admin may attribute the post to any member (or free-text real_name),
        # and it publishes immediately.
        subject_member_id = payload.subject_member_id
        if subject_member_id is not None and (
            db.query(Member.id).filter_by(id=subject_member_id).first() is None
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subject member not found"
            )
        real_name = payload.real_name
        post_status = PostStatus.ACCEPTED
    else:
        # Members post about themselves and need admin approval. Their
        # subject is always their own member — payload subject/real_name
        # are ignored so they can't attribute a post to someone else.
        if viewer_member_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="profile_incomplete"
            )
        subject_member_id = viewer_member_id
        real_name = None
        post_status = PostStatus.PENDING

    obj = Job(
        job_year=payload.job_year,
        job_month=payload.job_month,
        company=payload.company,
        category=payload.category,
        kind=JobKind(payload.kind),
        experience_md=payload.experience_md,
        real_name=real_name,
        subject_member_id=subject_member_id,
        author_user_id=current_user.id,
        is_anonymous=payload.is_anonymous,
        status=post_status,
        timeline_md=payload.timeline_md,
        # Pydantic gives us TimelineEvent instances containing date objects;
        # SQLAlchemy's JSON column needs plain JSON-serialisable dicts, so
        # mode="json" forces the date -> ISO string conversion.
        timeline_events=(
            [e.model_dump(mode="json") for e in payload.timeline_events]
            if payload.timeline_events is not None
            else None
        ),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    names = _subject_names(db, [obj.subject_member_id])
    return serialize_job(
        obj,
        is_admin=is_admin,
        viewer_member_id=viewer_member_id,
        attachment_count=0,
        subject_name=names.get(obj.subject_member_id),
    )


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> JobResponse:
    obj = _get_or_404(db, job_id)
    is_admin = current_user.role is UserRole.ADMIN
    viewer_member_id = _viewer_member_id(db, current_user)
    is_owner = (
        obj.subject_member_id is not None and obj.subject_member_id == viewer_member_id
    )
    if not is_admin and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your post"
        )

    # mode="json" so nested timeline dates arrive as ISO strings for the
    # JSON column — same boundary handling as create_job.
    data = payload.model_dump(exclude_unset=True, mode="json")
    if not is_admin:
        # Members cannot reassign a post to someone else or set a free-text
        # name — their subject stays themselves.
        data.pop("subject_member_id", None)
        data.pop("real_name", None)
    elif data.get("subject_member_id") is not None and (
        db.query(Member.id).filter_by(id=data["subject_member_id"]).first() is None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subject member not found"
        )

    for field, value in data.items():
        if field == "kind" and value is not None:
            value = JobKind(value)
        setattr(obj, field, value)
    obj.last_edited_by_user_id = current_user.id
    # An owner editing a rejected post resubmits it; editing an already
    # accepted (public) post sends it back for re-review so content can't
    # be changed out from under the approval. Admin edits stay as-is.
    if (
        not is_admin
        and is_owner
        and obj.status
        in (
            PostStatus.REJECTED,
            PostStatus.ACCEPTED,
        )
    ):
        obj.status = PostStatus.PENDING
        # Returning to the queue drops the previous review outcome so a stale
        # rejection reason (or old reviewer/timestamp) doesn't cling to it.
        obj.review_reason = None
        obj.reviewed_by_user_id = None
        obj.reviewed_at = None

    db.commit()
    db.refresh(obj)
    counts = _attachment_counts(db, [obj.id])
    names = _subject_names(db, [obj.subject_member_id])
    like_count, liked_by_me = _likes_map(db, [obj.id], current_user.id)[obj.id]
    return serialize_job(
        obj,
        is_admin=is_admin,
        viewer_member_id=viewer_member_id,
        attachment_count=counts.get(obj.id, 0),
        subject_name=names.get(obj.subject_member_id),
        like_count=like_count,
        liked_by_me=liked_by_me,
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    current_user: User = Depends(require_posting_member),
    payload: PasswordConfirmRequest | None = None,
) -> None:
    obj = _get_or_404(db, job_id)
    is_admin = current_user.role is UserRole.ADMIN
    viewer_member_id = _viewer_member_id(db, current_user)
    is_owner = (
        obj.subject_member_id is not None and obj.subject_member_id == viewer_member_id
    )
    if not is_admin and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your post"
        )
    if is_admin:
        # Admin re-auth for the destructive action; owners deleting their
        # own post don't need to re-enter a password.
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password is required",
            )
        require_admin_password(db, payload.password)
    db.delete(obj)
    db.commit()
    # DB rows for job_attachments cascade-delete via the FK, but the
    # on-disk files (originals + OnlyOffice preview PDFs) under
    # uploads/jobs/{id}/ are orphaned otherwise. Clean the whole
    # per-job directory after the DB commit succeeds — if rmtree
    # races against a concurrent upload the missing files will at
    # worst surface as 404s on download, not data loss.
    shutil.rmtree(job_uploads_dir(uploads_root, job_id), ignore_errors=True)


def _review(db: Session, job_id: int, admin: User, new_status, reason) -> JobResponse:
    obj = _get_or_404(db, job_id)
    obj.status = new_status
    obj.review_reason = reason
    obj.reviewed_by_user_id = admin.id
    obj.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(obj)
    counts = _attachment_counts(db, [obj.id])
    names = _subject_names(db, [obj.subject_member_id])
    like_count, liked_by_me = _likes_map(db, [obj.id], admin.id)[obj.id]
    return serialize_job(
        obj,
        is_admin=True,
        viewer_member_id=None,
        attachment_count=counts.get(obj.id, 0),
        subject_name=names.get(obj.subject_member_id),
        like_count=like_count,
        liked_by_me=liked_by_me,
    )


@router.post("/{job_id}/accept", response_model=JobResponse)
def accept_job(
    job_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> JobResponse:
    return _review(db, job_id, admin, PostStatus.ACCEPTED, None)


@router.post("/{job_id}/reject", response_model=JobResponse)
def reject_job(
    job_id: int,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> JobResponse:
    return _review(db, job_id, admin, PostStatus.REJECTED, payload.reason)
