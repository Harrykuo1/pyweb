from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import (
    require_admin_password,
    require_completed_member,
    require_posting_member,
)
from app.database import get_db
from app.models import Event, EventComment, Member, PostStatus, User, UserRole
from app.schemas import (
    EventCommentCreate,
    EventCommentResponse,
    EventCommentUpdate,
    PasswordConfirmRequest,
)

router = APIRouter(prefix="/api/events", tags=["event_comments"])


def _visible_event_or_404(db: Session, event_id: int, user: User) -> Event:
    """The event, but 404 if it's not visible to this viewer — same rule as
    events.get_event: admins see everything, others only accepted events plus
    their own. Keeps comments from leaking the existence of pending posts."""
    event = db.query(Event).filter_by(id=event_id).one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到活動")
    is_admin = user.role is UserRole.ADMIN
    is_owner = event.author_user_id is not None and event.author_user_id == user.id
    if not is_admin and event.status is not PostStatus.ACCEPTED and not is_owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到活動")
    return event


def _comment_or_404(db: Session, event_id: int, comment_id: int) -> EventComment:
    comment = (
        db.query(EventComment).filter_by(id=comment_id, event_id=event_id).one_or_none()
    )
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到留言")
    return comment


def _author_display_names(db: Session, author_ids: list[int | None]) -> dict[int, str]:
    """Map author_user_id -> a display name in one query. Prefers the member's
    real name, then Discord global name / handle, then legacy username — so
    every commenter (including profileless admins) shows a name."""
    ids = [a for a in author_ids if a is not None]
    if not ids:
        return {}
    rows = (
        db.query(
            User.id,
            Member.real_name,
            User.discord_global_name,
            User.discord_username,
            User.username,
        )
        .outerjoin(Member, Member.user_id == User.id)
        .filter(User.id.in_(ids))
        .all()
    )
    out: dict[int, str] = {}
    for uid, real_name, global_name, handle, username in rows:
        out[uid] = real_name or global_name or handle or username or "未知成員"
    return out


def _to_response(
    comment: EventComment,
    *,
    is_admin: bool,
    viewer_user_id: int,
    author_name: str | None,
) -> EventCommentResponse:
    is_author = (
        comment.author_user_id is not None and comment.author_user_id == viewer_user_id
    )
    return EventCommentResponse(
        id=comment.id,
        event_id=comment.event_id,
        body=comment.body,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
        author_display_name=author_name,
        author_user_id=comment.author_user_id if is_admin else None,
        can_edit=is_author,
        can_delete=is_admin or is_author,
    )


@router.get("/{event_id}/comments", response_model=list[EventCommentResponse])
def list_comments(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
) -> list[EventCommentResponse]:
    _visible_event_or_404(db, event_id, current_user)
    comments = (
        db.query(EventComment)
        .filter_by(event_id=event_id)
        .order_by(EventComment.id.asc())
        .all()
    )
    is_admin = current_user.role is UserRole.ADMIN
    names = _author_display_names(db, [c.author_user_id for c in comments])
    return [
        _to_response(
            c,
            is_admin=is_admin,
            viewer_user_id=current_user.id,
            author_name=names.get(c.author_user_id),
        )
        for c in comments
    ]


@router.post(
    "/{event_id}/comments",
    response_model=EventCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    event_id: int,
    payload: EventCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> EventCommentResponse:
    _visible_event_or_404(db, event_id, current_user)
    # Comments publish immediately — no review queue, unlike events themselves.
    comment = EventComment(
        event_id=event_id,
        author_user_id=current_user.id,
        body=payload.body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    names = _author_display_names(db, [comment.author_user_id])
    return _to_response(
        comment,
        is_admin=current_user.role is UserRole.ADMIN,
        viewer_user_id=current_user.id,
        author_name=names.get(comment.author_user_id),
    )


@router.put("/{event_id}/comments/{comment_id}", response_model=EventCommentResponse)
def update_comment(
    event_id: int,
    comment_id: int,
    payload: EventCommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> EventCommentResponse:
    comment = _comment_or_404(db, event_id, comment_id)
    # Only the author edits their own words — not even an admin rewrites
    # someone else's comment (admins moderate by deleting, not editing).
    if comment.author_user_id is None or comment.author_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="不能編輯別人的留言"
        )
    comment.body = payload.body
    comment.edited_at = datetime.now(UTC)
    db.commit()
    db.refresh(comment)
    names = _author_display_names(db, [comment.author_user_id])
    return _to_response(
        comment,
        is_admin=current_user.role is UserRole.ADMIN,
        viewer_user_id=current_user.id,
        author_name=names.get(comment.author_user_id),
    )


@router.delete(
    "/{event_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_comment(
    event_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
    payload: PasswordConfirmRequest | None = None,
) -> None:
    comment = _comment_or_404(db, event_id, comment_id)
    is_admin = current_user.role is UserRole.ADMIN
    is_author = (
        comment.author_user_id is not None and comment.author_user_id == current_user.id
    )
    if not is_admin and not is_author:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="不能刪除別人的留言"
        )
    # Authors delete their own comment freely; an admin moderating someone
    # else's re-authenticates with the admin password (mirrors events/photos).
    if is_admin and not is_author:
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password is required",
            )
        require_admin_password(db, payload.password)
    db.delete(comment)
    db.commit()
