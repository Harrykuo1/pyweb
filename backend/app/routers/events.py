import shutil
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.core.deps import require_admin, require_completed_member
from app.core.search_query import build_ilike_filter
from app.core.search_query import parse as parse_search_query
from app.core.security import verify_password
from app.database import get_db
from app.models import Event, EventPhoto, EventTag, User
from app.routers.event_photos import event_uploads_dir, get_uploads_root
from app.schemas import (
    EventCreate,
    EventResponse,
    EventUpdate,
    ListResponse,
    PasswordConfirmRequest,
)

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


def _to_response(
    event: Event, tags: list[str], photo_count: int, cover_photo_id: int | None
) -> EventResponse:
    # Build explicitly rather than model_validate(event): the response's
    # `tags: list[str]` field would otherwise try to coerce the ORM
    # `tags` relationship (a list of EventTag objects) and fail.
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
    )


def _serialize_many(db: Session, events: list[Event]) -> list[EventResponse]:
    ids = [e.id for e in events]
    tags = _tags_map(db, ids)
    aggregates = _photo_aggregates(db, ids)
    out = []
    for e in events:
        count, cover = aggregates.get(e.id, (0, None))
        out.append(_to_response(e, tags.get(e.id, []), count, cover))
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
    q: str | None = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    _: object = Depends(require_completed_member),
) -> ListResponse[EventResponse]:
    query = db.query(Event)

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
        items=_serialize_many(db, items),
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
    _: object = Depends(require_completed_member),
) -> EventResponse:
    obj = _get_or_404(db, event_id)
    return _serialize_many(db, [obj])[0]


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> EventResponse:
    obj = Event(
        title=payload.title,
        event_date=payload.event_date,
        location=payload.location,
        description_md=payload.description_md,
    )
    db.add(obj)
    db.flush()
    _set_tags(db, obj, payload.tags)
    db.commit()
    db.refresh(obj)
    # Freshly created — no photos can exist yet, so the 0 / None defaults
    # are exact. Skip the aggregate query for this path.
    return _to_response(obj, payload.tags, 0, None)


@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> EventResponse:
    obj = _get_or_404(db, event_id)
    data = payload.model_dump(exclude_unset=True)
    tags = data.pop("tags", None)
    for field, value in data.items():
        setattr(obj, field, value)
    if tags is not None:
        _set_tags(db, obj, tags)
    db.commit()
    db.refresh(obj)
    return _serialize_many(db, [obj])[0]


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    payload: PasswordConfirmRequest,
    db: Session = Depends(get_db),
    uploads_root: Path = Depends(get_uploads_root),
    admin: User = Depends(require_admin),
) -> None:
    _require_admin_password(payload, admin)
    obj = _get_or_404(db, event_id)
    db.delete(obj)
    db.commit()
    # tag/photo rows cascade via the FK; the on-disk photo files under
    # uploads/events/{id}/ are orphaned otherwise, so clear the whole
    # per-event directory after the DB commit succeeds.
    shutil.rmtree(event_uploads_dir(uploads_root, event_id), ignore_errors=True)
