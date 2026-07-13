from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import require_completed_member, require_posting_member
from app.core.member_display import member_display_map
from app.database import get_db
from app.models import Event, EventLike, PostStatus, User, UserRole
from app.schemas import LikerResponse, LikeStatusResponse

router = APIRouter(prefix="/api/events", tags=["event_likes"])


def _visible_event_or_404(db: Session, event_id: int, user: User) -> Event:
    # Mirrors event_comments._visible_event_or_404; both fold into one shared
    # helper when likes + comments are ported to jobs.
    event = db.query(Event).filter_by(id=event_id).one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到活動")
    is_admin = user.role is UserRole.ADMIN
    is_owner = event.author_user_id is not None and event.author_user_id == user.id
    if not is_admin and event.status is not PostStatus.ACCEPTED and not is_owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到活動")
    return event


def _like_count(db: Session, event_id: int) -> int:
    return db.query(func.count(EventLike.id)).filter_by(event_id=event_id).scalar() or 0


@router.post("/{event_id}/like", response_model=LikeStatusResponse)
def like_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> LikeStatusResponse:
    _visible_event_or_404(db, event_id, current_user)
    existing = (
        db.query(EventLike)
        .filter_by(event_id=event_id, user_id=current_user.id)
        .one_or_none()
    )
    if existing is None:
        db.add(EventLike(event_id=event_id, user_id=current_user.id))
        try:
            db.commit()
        except IntegrityError:
            # A concurrent request from the same user already inserted the row;
            # the unique constraint makes the second insert a no-op.
            db.rollback()
    return LikeStatusResponse(like_count=_like_count(db, event_id), liked=True)


@router.delete("/{event_id}/like", response_model=LikeStatusResponse)
def unlike_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_posting_member),
) -> LikeStatusResponse:
    _visible_event_or_404(db, event_id, current_user)
    existing = (
        db.query(EventLike)
        .filter_by(event_id=event_id, user_id=current_user.id)
        .one_or_none()
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
    return LikeStatusResponse(like_count=_like_count(db, event_id), liked=False)


@router.get("/{event_id}/likes", response_model=list[LikerResponse])
def list_likers(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
) -> list[LikerResponse]:
    _visible_event_or_404(db, event_id, current_user)
    # Most recent likers first.
    user_ids = [
        uid
        for (uid,) in db.query(EventLike.user_id)
        .filter_by(event_id=event_id)
        .order_by(EventLike.id.desc())
    ]
    infos = member_display_map(db, user_ids)
    out: list[LikerResponse] = []
    for uid in user_ids:
        info = infos.get(uid, {})
        out.append(
            LikerResponse(
                user_id=uid,
                display_name=info.get("name"),
                member_id=info.get("member_id"),
                has_photo=info.get("has_photo", False),
                photo_updated_at=info.get("photo_updated_at"),
            )
        )
    return out
