import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core import audit_log, discord_link, discord_oauth
from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.core.rate_limit import limiter
from app.core.runtime_config import DISCORD_GUILD_ID_KEY, get_str
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.models import Member, PendingDiscordLink, User, UserRole
from app.schemas import (
    LoginRequest,
    PendingLinkResponse,
    ResolvePendingLinkRequest,
    RoleUpdateRequest,
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
    ip = audit_log.client_ip(request)

    # bcrypt hashes are salted, so we cannot index by them. Two seeded
    # accounts means the linear scan is fine; revisit if the user count grows.
    for user in db.query(User).all():
        if verify_password(payload.password, user.password_hash):
            request.session["user_id"] = user.id
            request.session["role"] = user.role.value
            request.session["password_version"] = user.password_version
            audit_log.record_success(ip, role=user.role.value)
            return user

    audit_log.record_failure(ip)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid password",
    )


# Browser lands here on any failed Discord login; the frontend login page
# reads ?error=<reason> to show a message. "/" on success.
_LOGIN_PATH = "/login"
_HOME_PATH = "/"


def _oauth_error(reason: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"{_LOGIN_PATH}?error={reason}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/discord/login")
def discord_login(request: Request) -> Response:
    if not settings.discord_oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discord login is not configured",
        )
    state = secrets.token_urlsafe(32)
    request.session["discord_oauth_state"] = state
    return RedirectResponse(
        url=discord_oauth.build_authorize_url(state),
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/discord/callback")
def discord_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    if not settings.discord_oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discord login is not configured",
        )

    # User denied consent on Discord's side.
    if error is not None:
        return _oauth_error("discord_denied")

    # CSRF: the state we stored before redirecting must come back intact.
    expected_state = request.session.pop("discord_oauth_state", None)
    if not state or not expected_state or state != expected_state:
        return _oauth_error("state_mismatch")
    if not code:
        return _oauth_error("missing_code")

    token = discord_oauth.exchange_code(code)
    if token is None:
        return _oauth_error("token_exchange_failed")

    identity = discord_oauth.fetch_identity(token)
    if identity is None:
        return _oauth_error("identity_failed")

    # Re-verify guild membership on every login: leaving the guild revokes
    # access immediately.
    guild_id = get_str(db, DISCORD_GUILD_ID_KEY)
    if not guild_id:
        return _oauth_error("guild_not_configured")
    if not discord_oauth.is_guild_member(token, guild_id):
        return _oauth_error("not_member")

    user = db.query(User).filter_by(discord_id=identity.id).one_or_none()
    if user is None:
        # First login of a pre-created account: bridge by the resume handle.
        # On a unique match we get the now-linked user; otherwise the
        # identity is queued for an admin and we turn them away.
        user = discord_link.link_or_queue(db, identity)
        if user is None:
            return _oauth_error("not_linked")

    request.session["user_id"] = user.id
    request.session["role"] = user.role.value
    request.session["password_version"] = user.password_version
    audit_log.record_success(audit_log.client_ip(request), role=user.role.value)
    return RedirectResponse(url=_HOME_PATH, status_code=status.HTTP_302_FOUND)


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


@router.get("/pending-links", response_model=list[PendingLinkResponse])
def list_pending_links(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[PendingDiscordLink]:
    return (
        db.query(PendingDiscordLink).order_by(PendingDiscordLink.first_seen_at).all()
    )


@router.post("/pending-links/{discord_id}/resolve", response_model=UserResponse)
def resolve_pending_link(
    discord_id: str,
    payload: ResolvePendingLinkRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    pending = (
        db.query(PendingDiscordLink).filter_by(discord_id=discord_id).one_or_none()
    )
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pending link not found"
        )
    member = db.query(Member).filter_by(id=payload.member_id).one_or_none()
    if member is None or member.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member account not found"
        )
    user = db.query(User).filter_by(id=member.user_id).one()
    if user.discord_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Member already linked"
        )

    user.discord_id = pending.discord_id
    user.discord_username = pending.discord_username
    user.discord_global_name = pending.discord_global_name
    user.pending_discord_username = None
    db.delete(pending)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: RoleUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    # Only admin/member are assignable; the legacy shared VIEWER role is
    # not something we promote individuals into.
    if payload.role not in (UserRole.ADMIN, UserRole.MEMBER):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role must be admin or member",
        )
    user = db.query(User).filter_by(id=user_id).one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    # Lockout guard: never demote the last remaining admin.
    if user.role is UserRole.ADMIN and payload.role is not UserRole.ADMIN:
        admin_count = db.query(User).filter_by(role=UserRole.ADMIN).count()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot demote the last admin",
            )
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    if not verify_password(payload.current_password, current_user.password_hash):
        # 422, not 401, so the global axios auth-interceptor doesn't
        # treat a typo'd current password as an expired session — the
        # session is still valid here, only the body-supplied password
        # didn't validate.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
    # Bump the version so any session signed with the old number gets
    # rejected by get_current_user. Other devices for this user — and
    # any attacker holding a stolen cookie — get evicted on their next
    # request.
    target.password_version += 1
    db.commit()

    # When the admin rotates their own password, re-stamp the current
    # session with the new version so this browser stays logged in.
    # Other sessions for the same admin still get evicted.
    if target.id == current_user.id:
        request.session["password_version"] = target.password_version

    return Response(status_code=status.HTTP_204_NO_CONTENT)
