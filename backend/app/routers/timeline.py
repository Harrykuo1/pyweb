from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.deps import require_completed_member
from app.core.job_serialize import job_display_name
from app.core.member_display import member_display_map
from app.core.post_visibility import event_visibility_filter
from app.database import get_db
from app.models import Event, EventComment, Job, Member, PostStatus, User, UserRole
from app.schemas.timeline import (
    EventChangedItem,
    EventCommentItem,
    JobCreatedItem,
    MemberJoinedItem,
    TimelineItem,
    TimelineResponse,
)

router = APIRouter(prefix="/api/timeline", tags=["timeline"])

TIMELINE_LIMIT_DEFAULT = 10
TIMELINE_LIMIT_MAX = 50


@router.get("", response_model=TimelineResponse)
def list_timeline(
    limit: int = Query(default=TIMELINE_LIMIT_DEFAULT, ge=1, le=TIMELINE_LIMIT_MAX),
    before: datetime | None = Query(default=None),
    # Set by the frontend when an admin is previewing as a member, so the feed
    # renders exactly what a member sees (no pending posts, anonymous authors
    # masked, suspended members' joins hidden) instead of the admin's view.
    preview: bool = Query(default=False),
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
    # global top N (older than `before`) cannot include rows past any
    # source's own top N.
    is_admin = current_user.role is UserRole.ADMIN
    # Preview-as-member drops admin privileges for this feed's visibility.
    effective_admin = is_admin and not preview
    vm = db.query(Member.id).filter_by(user_id=current_user.id).first()
    viewer_member_id = vm[0] if vm is not None else None

    members_q = db.query(Member).order_by(Member.joined_at.desc())
    # Non-admins (incl. preview) don't see suspended members anywhere else, so
    # keep their join events out of the feed too. Legacy rows (no account) and
    # active accounts stay.
    if not effective_admin:
        members_q = members_q.outerjoin(User, Member.user_id == User.id).filter(
            or_(Member.user_id.is_(None), User.is_active.is_(True))
        )
    jobs_q = db.query(Job).order_by(Job.created_at.desc())
    # Non-admins never see unaccepted posts in the feed (their own aside).
    if not effective_admin:
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
            # §8: anonymous posts expose no author name to non-admins
            # (and not to an admin who is previewing as a member).
            real_name=job_display_name(
                j,
                is_admin=effective_admin,
                subject_name=subj_names.get(j.subject_member_id),
            ),
            job_year=j.job_year,
            job_month=j.job_month,
        )
        for j in jobs
    ]

    visibility = event_visibility_filter(current_user.id, is_admin=effective_admin)
    event_items: list[TimelineItem] = []
    for event_type, timestamp_column, actor_column in (
        ("event_created", Event.created_at, Event.author_user_id),
        ("event_updated", Event.edited_at, Event.last_edited_by_user_id),
    ):
        query = db.query(Event, actor_column).filter(
            visibility, timestamp_column.is_not(None)
        )
        if before is not None:
            query = query.filter(timestamp_column < before)
        rows = (
            query.order_by(timestamp_column.desc(), Event.id.desc()).limit(peek).all()
        )
        authors = member_display_map(db, [actor_id for _, actor_id in rows])
        event_items.extend(
            EventChangedItem(
                type=event_type,
                timestamp=event.created_at
                if event_type == "event_created"
                else event.edited_at,
                event_id=event.id,
                title=event.title,
                real_name=authors.get(actor_id, {}).get("name"),
            )
            for event, actor_id in rows
        )

    comment_time = func.coalesce(EventComment.edited_at, EventComment.created_at)
    comments_q = (
        db.query(EventComment, Event.title)
        .join(Event, Event.id == EventComment.event_id)
        .filter(visibility)
    )
    if before is not None:
        comments_q = comments_q.filter(comment_time < before)
    comments = (
        comments_q.order_by(comment_time.desc(), EventComment.id.desc())
        .limit(peek)
        .all()
    )
    authors = member_display_map(db, [c.author_user_id for c, _ in comments])
    event_items.extend(
        EventCommentItem(
            type="event_comment_updated" if c.edited_at else "event_comment_created",
            timestamp=c.edited_at or c.created_at,
            event_id=c.event_id,
            title=title,
            real_name=authors.get(c.author_user_id, {}).get("name"),
            comment_id=c.id,
            body=c.body[:160],
        )
        for c, title in comments
    )

    merged = sorted(
        member_items + job_items + event_items,
        key=lambda x: x.timestamp,
        reverse=True,
    )[:peek]
    has_more = len(merged) > limit
    return TimelineResponse(items=merged[:limit], has_more=has_more)
