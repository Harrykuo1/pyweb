from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.rate_limit import limiter
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    LoginRequest,
    UpdatePasswordRequest,
    UpdateUsernameRequest,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Per-IP brute-force throttle. 5/minute is generous enough that real users
# never hit it (login is once per session) and tight enough that a typical
# bcrypt-bottlenecked attacker can't sweep a password space against the
# two seeded accounts in any reasonable wall-clock budget. Successes count
# too — simpler, and a real user logging in 5 times in a minute is unusual.
LOGIN_RATE_LIMIT = "5/minute"


def _get_user_by_role(db: Session, role: UserRole) -> User:
    user = db.query(User).filter_by(role=role).one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user with role '{role.value}'",
        )
    return user


@router.post("/login", response_model=UserResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> User:
    # bcrypt hashes are salted, so we cannot index by them. Two seeded
    # accounts means the linear scan is fine; revisit if the user count grows.
    for user in db.query(User).all():
        if verify_password(payload.password, user.password_hash):
            request.session["user_id"] = user.id
            request.session["role"] = user.role.value
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid password",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[User]:
    return db.query(User).order_by(User.id).all()


@router.patch("/users/{role}/username", response_model=UserResponse)
def update_username(
    role: UserRole,
    payload: UpdateUsernameRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    target = _get_user_by_role(db, role)

    new_username = payload.username.strip()
    if not new_username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username cannot be blank",
        )

    if new_username != target.username:
        clash = (
            db.query(User)
            .filter(User.username == new_username, User.id != target.id)
            .one_or_none()
        )
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

    target.username = new_username
    db.commit()
    db.refresh(target)
    return target


@router.patch("/users/{role}/password", status_code=status.HTTP_204_NO_CONTENT)
def update_password(
    role: UserRole,
    payload: UpdatePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    target = _get_user_by_role(db, role)

    # Login is identified by password alone (linear scan over users), so two
    # accounts sharing a password would make login ambiguous.
    for other in db.query(User).filter(User.id != target.id).all():
        if verify_password(payload.new_password, other.password_hash):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="New password collides with another account",
            )

    target.password_hash = hash_password(payload.new_password)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
