import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.core.deps import (
    require_admin,
    require_completed_member,
    require_posting_member,
)
from app.core.search_query import build_ilike_filter
from app.core.search_query import parse as parse_search_query
from app.core.security import verify_password
from app.database import get_db
from app.models import Event, EventPhoto, EventTag, Member, PostStatus, User, UserRole
from app.routers.event_photos import event_uploads_dir, get_uploads_root
from app.schemas import (
    EventCreate,
    EventResponse,
    EventUpdate,
    ListResponse,
    PasswordConfirmRequest,
    RejectRequest,
)
from app.schemas.job import PostStatusLiteral

router = APIRouter(prefix="/api/events", tags=["events"])

SortField = Literal["event_date", "created_at", "title"]
SortOrder = Literal["asc", "desc"]

_SORT_COLUMNS = {
    "event_date": Event.event_date,
    "created_at": Event.created_at,
    "title": Event.title,
}

TAGS_AUTOCOMPLETE_LIMIT = 50


def _get_or_404(db: Session, event_id: int) -> Event:
    obj = db.query(Event).filter_by(id=event_id).one_or_none()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return obj


def _tags_map(db: Session, event_ids: list[int]) -> dict[int, list[str]]:
    if not event_ids:
        return {}
    rows = (
        db.query(EventTag.event_id, EventTag.name)
        .filter(EventTag.event_id.in_(event_ids))
        .order_by(EventTag.event_id, EventTag.name)
        .all()
    )
    out: dict[int, list[str]] = {}
    for event_id, name in rows:
        out.setdefault(event_id, []).append(name)
    return out


def _photo_aggregates(db: Session, event_ids: list[int]) -> dict[int, tuple[int, int]]:
    """Return {event_id: (photo_count, cover_photo_id)} in one query.
    Cover is the earliest photo by id; events with no photos are absent
    from the map so the caller defaults via dict.get."""
    if not event_ids:
        return {}
    rows = (
        db.query(
            EventPhoto.event_id,
            func.count(EventPhoto.id),
            func.min(EventPhoto.id),
        )
        .filter(EventPhoto.event_id.in_(event_ids))
        .group_by(EventPhoto.event_id)
        .all()
    )
    return {event_id: (count, cover) for event_id, count, cover in rows}


def _author_names(db: Session, author_ids: list[int | None]) -> dict[int, str]:
    """Map author_user_id -> the author's member real_name. Authors without
    a member profile (e.g. an admin) are absent → displayed as None."""
    ids = [a for a in author_ids if a is not None]
    if not ids:
        return {}
    rows = (
        db.query(User.id, Member.real_name)
        .join(Member, Member.user_id == User.id)
        .filter(User.id.in_(ids))
        .all()
    )
    return dict(rows)


def _to_response(
    event: Event,
    *,
    is_admin: bool,
    viewer_user_id: int,
    author_name: str | None,
    tags: list[str],
    photo_count: int,
    cover_photo_id: int | None,
) -> EventResponse:
    # Build explicitly rather than model_validate(event): the response's
    # `tags: list[str]` field would otherwise try to coerce the ORM
    # `tags` relationship (a list of EventTag objects) and fail.
    is_owner = (
        event.author_user_id is not None and event.author_user_id == viewer_user_id
    )
    return EventResponse(
        id=event.id,
        title=event.title,
        event_date=event.event_date,
        location=event.location,
        description_md=event.description_md,
        created_at=event.created_at,
        tags=tags,
        photo_count=photo_count,
        cover_photo_id=cover_photo_id,
        author_display_name=author_name,
        status=event.status.value,
        review_reason=event.review_reason if (is_admin or is_owner) else None,
        can_edit=is_admin or is_owner,
        author_user_id=event.author_user_id if is_admin else None,
    )


def _serialize_many(
    db: Session, events: list[Event], *, is_admin: bool, viewer_user_id: int
) -> list[EventResponse]:
    ids = [e.id for e in events]
    tags = _tags_map(db, ids)
    aggregates = _photo_aggregates(db, ids)
    authors = _author_names(db, [e.author_user_id for e in events])
    out = []
    for e in events:
        count, cover = aggregates.get(e.id, (0, None))
        out.append(
            _to_response(
                e,
                is_admin=is_admin,
                viewer_user_id=viewer_user_id,
                author_name=authors.get(e.author_user_id),
                tags=tags.get(e.id, []),
                photo_count=count,
                cover_photo_id=cover,
            )
        )
    return out


def _set_tags(db: Session, event: Event, names: list[str]) -> None:
    """Replace an event's tags with the given normalized names. Schema
    validation has already trimmed / deduplicated; here we just swap the
    association rows."""
    event.tags.clear()
    db.flush()
    for name in names:
        event.tags.append(EventTag(name=name))


def _require_admin_password(payload: PasswordConfirmRequest, admin: User) -> None:
    if not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Password is incorrect",
        )


@router.get("", response_model=ListResponse[EventResponse])
def list_events(
    sort: SortField = "event_date",
    order: SortOrder = "desc",
    year: int | None = None,
    # Repeatable: ?tag=A&tag=B → events carrying ANY of the selected tags.
    tag: list[str] = Query(default_factory=list, max_length=20),
    status_filter: PostStatusLiteral | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
) -> ListResponse[EventResponse]:
    is_admin = current_user.role is UserRole.ADMIN
    query = db.query(Event)

    # Visibility: non-admins see accepted events plus their own.
    if not is_admin:
        query = query.filter(
            (Event.status == PostStatus.ACCEPTED)
            | (Event.author_user_id == current_user.id)
        )
    if status_filter is not None:
        query = query.filter(Event.status == PostStatus(status_filter))

    if year is not None:
        query = query.filter(extract("year", Event.event_date) == year)
    if tag:
        # Match events that have at least one of the requested tags. The
        # join can fan out a row per matching tag, so distinct() collapses
        # back to one row per event.
        query = (
            query.join(EventTag, EventTag.event_id == Event.id)
            .filter(EventTag.name.in_(tag))
            .distinct()
        )
    if q:
        expr = build_ilike_filter(
            parse_search_query(q),
            [Event.title, Event.location, Event.description_md],
        )
        if expr is not None:
            query = query.filter(expr)

    column = _SORT_COLUMNS[sort]
    primary = column.asc() if order == "asc" else column.desc()
    if sort == "event_date":
        # created_at as a stable tiebreaker so same-day events keep a
        # deterministic order (most recently recorded first within a day).
        order_by = [primary, Event.created_at.desc()]
    else:
        order_by = [primary, Event.id.desc()]

    items = query.order_by(*order_by).all()
    return ListResponse[EventResponse](
        items=_serialize_many(
            db, items, is_admin=is_admin, viewer_user_id=current_user.id
        ),
        total=len(items),
    )


@router.get("/tags", response_model=list[str])
def list_tags(
    prefix: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
    _: object = Depends(require_completed_member),
) -> list[str]:
    query = db.query(EventTag.name).distinct()
    if prefix:
        query = query.filter(EventTag.name.ilike(f"{prefix}%"))
    rows = query.order_by(EventTag.name).limit(TAGS_AUTOCOMPLETE_LIMIT).all()
    return [row[0] for row in rows]


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
) -> EventResponse:
    obj = _get_or_404(db, event_id)
    is_admin = current_user.role is UserRole.ADMIN
    is_owner = (
        obj.author_user_id is not None and obj.author_user_id == current_user.id
    )
    if not is_admin and obj.status is not PostStatus.ACCEPTED and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return _serialize_many(
        db, [obj], is_admin=is_admin, viewer_user_id=current_user.id
    )[0]


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> EventResponse:
    is_admin = current_user.role is UserRole.ADMIN
    obj = Event(
        title=payload.title,
        event_date=payload.event_date,
        location=payload.location,
        description_md=payload.description_md,
        author_user_id=current_user.id,
        # Members need admin approval; admin posts publish immediately.
        status=PostStatus.ACCEPTED if is_admin else PostStatus.PENDING,
    )
    db.add(obj)
    db.flush()
    _set_tags(db, obj, payload.tags)
    db.commit()
    db.refresh(obj)
    names = _author_names(db, [obj.author_user_id])
    return _to_response(
        obj,
        is_admin=is_admin,
        viewer_user_id=current_user.id,
        author_name=names.get(obj.author_user_id),
        tags=payload.tags,
        photo_count=0,
        cover_photo_id=None,
    )


@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> EventResponse:
    obj = _get_or_404(db, event_id)
    is_admin = current_user.role is UserRole.ADMIN
    is_owner = (
        obj.author_user_id is not None and obj.author_user_id == current_user.id
    )
    if not is_admin and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your event"
        )
    data = payload.model_dump(exclude_unset=True)
    tags = data.pop("tags", None)
    for field, value in data.items():
        setattr(obj, field, value)
    if tags is not None:
        _set_tags(db, obj, tags)
    obj.last_edited_by_user_id = current_user.id
    # Owner editing a rejected event resubmits it; editing an already
    # accepted (public) event sends it back for re-review so content can't
    # be changed out from under the approval. Admin edits stay as-is.
    if not is_admin and is_owner and obj.status in (
        PostStatus.REJECTED,
        PostStatus.ACCEPTED,
    ):
        obj.status = PostStatus.PENDING
        # Returning to the queue drops the previous review outcome so a stale
        # rejection reason (or old reviewer/timestamp) doesn't cling to it.
        obj.review_reason = None
        obj.reviewed_by_user_id = None
        obj.reviewed_at = None
    db.commit()
    db.refresh(obj)
    return _serialize_many(
        db, [obj], is_admin=is_admin, viewer_user_id=current_user.id
    )[0]


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    current_user: User = Depends(require_posting_member),
    payload: PasswordConfirmRequest | None = None,
) -> None:
    obj = _get_or_404(db, event_id)
    is_admin = current_user.role is UserRole.ADMIN
    is_owner = (
        obj.author_user_id is not None and obj.author_user_id == current_user.id
    )
    if not is_admin and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your event"
        )
    if is_admin:
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password is required",
            )
        _require_admin_password(payload, current_user)
    db.delete(obj)
    db.commit()
    # tag/photo rows cascade via the FK; the on-disk photo files under
    # uploads/events/{id}/ are orphaned otherwise, so clear the whole
    # per-event directory after the DB commit succeeds.
    shutil.rmtree(event_uploads_dir(uploads_root, event_id), ignore_errors=True)


def _review(
    db: Session, event_id: int, admin: User, new_status, reason: str | None
) -> EventResponse:
    obj = _get_or_404(db, event_id)
    obj.status = new_status
    obj.review_reason = reason
    obj.reviewed_by_user_id = admin.id
    obj.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(obj)
    return _serialize_many(db, [obj], is_admin=True, viewer_user_id=admin.id)[0]


@router.post("/{event_id}/accept", response_model=EventResponse)
def accept_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> EventResponse:
    return _review(db, event_id, admin, PostStatus.ACCEPTED, None)


@router.post("/{event_id}/reject", response_model=EventResponse)
def reject_event(
    event_id: int,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> EventResponse:
    return _review(db, event_id, admin, PostStatus.REJECTED, payload.reason)
