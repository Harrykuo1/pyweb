from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Member, User, UserRole


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = db.query(User).filter_by(id=user_id).one_or_none()
    if user is None:
        # Session points at a deleted user; clear it so the client re-logs in.
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session user no longer exists",
        )
    # Stale-session check: session was signed before the user's last
    # password rotation, so it's been invalidated on purpose. Includes
    # the missing-key case, which covers cookies issued before this
    # mechanism was deployed.
    if request.session.get("password_version") != user.password_version:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired due to password change",
        )
    if not user.is_active:
        # Admin suspended this account — evict the session immediately.
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account suspended",
        )
    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role is not UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


def require_member(
    current_user: User = Depends(get_current_user),
) -> User:
    # Posting (jobs/events) is open to real members and admins. The legacy
    # shared VIEWER account stays read-only during the transition.
    if current_user.role not in (UserRole.ADMIN, UserRole.MEMBER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Member role required",
        )
    return current_user


def require_completed_member(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    # New members must finish their profile before they can see any data.
    # Admins and the legacy viewer account have no profile and are exempt.
    if current_user.role is UserRole.MEMBER:
        has_profile = (
            db.query(Member.id).filter_by(user_id=current_user.id).first()
            is not None
        )
        if not has_profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="profile_incomplete",
            )
    return current_user
