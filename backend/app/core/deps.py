from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import verify_password
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
            db.query(Member.id).filter_by(user_id=current_user.id).first() is not None
        )
        if not has_profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="profile_incomplete",
            )
    return current_user


def require_posting_member(
    current_user: User = Depends(require_member),
    db: Session = Depends(get_db),
) -> User:
    # Gate for creating/editing job & event content. require_member already
    # rejects the read-only viewer; on top of that a member must have
    # completed their profile, otherwise a profileless account could publish
    # content while never appearing in the members-first admin roster. Unlike
    # require_completed_member (used by read endpoints), this does NOT exempt
    # the viewer — viewers stay read-only.
    if current_user.role is UserRole.MEMBER:
        has_profile = (
            db.query(Member.id).filter_by(user_id=current_user.id).first() is not None
        )
        if not has_profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="profile_incomplete",
            )
    return current_user


def admin_password_account(db: Session) -> User | None:
    """The break-glass password admin — the one admin-role account that still
    has a password (Discord-linked admins have none). Its password is the
    shared confirmation credential for destructive/account actions, so any
    admin — even a Discord-linked one with no password of their own — can
    confirm by entering the admin password."""
    return (
        db.query(User)
        .filter(User.role == UserRole.ADMIN, User.password_hash.isnot(None))
        .order_by(User.id)
        .first()
    )


def verify_admin_password(db: Session, password: str) -> bool:
    """True if `password` matches THE admin account's password (not the acting
    user's own). Confirmation flows verify against this so a Discord-linked
    admin can still re-authenticate destructive actions."""
    account = admin_password_account(db)
    return account is not None and verify_password(password, account.password_hash)


def require_admin_password(db: Session, password: str) -> None:
    """Raise 422 unless `password` matches the admin account's password. 422
    (not 401) so the axios auth-interceptor doesn't treat a typo'd
    confirmation password as an expired session."""
    if not verify_admin_password(db, password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Password is incorrect",
        )
