import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core import audit_log, discord_link, discord_oauth, discord_register
from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.core.rate_limit import limiter
from app.core.runtime_config import DISCORD_GUILD_ID_KEY, get_str, set_str
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.models import Member, PendingDiscordLink, RegistrationInvite, User, UserRole
from app.schemas import (
    GuildConfigResponse,
    GuildConfigUpdate,
    LoginRequest,
    PendingLinkResponse,
    RegistrationInviteResponse,
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
# New registrants land here to fill in their member profile.
_REGISTER_PROFILE_PATH = "/register/profile"


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


@router.get("/discord/register")
def discord_register_start(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    if not settings.discord_oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discord login is not configured",
        )
    invite = db.query(RegistrationInvite).filter_by(token=token).one_or_none()
    if not discord_register.invite_is_valid(invite, datetime.now(UTC)):
        return _oauth_error("invalid_invite")

    state = secrets.token_urlsafe(32)
    request.session["discord_oauth_state"] = state
    request.session["registration_invite_token"] = token
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

    # Consume both single-use session values up front so any early return
    # below leaves no stale registration intent behind — otherwise a failed
    # registration could later hijack a normal login into a registration.
    expected_state = request.session.pop("discord_oauth_state", None)
    invite_token = request.session.pop("registration_invite_token", None)
    # CSRF: the state we stored before redirecting must come back intact.
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
    membership = discord_oauth.check_guild_membership(token, guild_id)
    if membership == "error":
        # Transient failure (rate limit / Discord hiccup) — not the same as
        # "not a member", so don't wrongly turn away a real member.
        return _oauth_error("guild_check_failed")
    if membership != "member":
        return _oauth_error("not_member")

    # Registration (invite consumed above) takes priority over login: a
    # fresh Discord identity coming through an invite becomes a new member.
    if invite_token is not None:
        user, err = discord_register.register_via_invite(db, identity, invite_token)
        if err is not None:
            return _oauth_error(err)
        redirect_target = _REGISTER_PROFILE_PATH
    else:
        user = db.query(User).filter_by(discord_id=identity.id).one_or_none()
        if user is None:
            # First login of a pre-created account: bridge by the resume
            # handle. On a unique match we get the now-linked user;
            # otherwise the identity is queued for an admin and turned away.
            user = discord_link.link_or_queue(db, identity)
            if user is None:
                return _oauth_error("not_linked")
        redirect_target = _HOME_PATH

    request.session["user_id"] = user.id
    request.session["role"] = user.role.value
    request.session["password_version"] = user.password_version
    audit_log.record_success(audit_log.client_ip(request), role=user.role.value)
    return RedirectResponse(url=redirect_target, status_code=status.HTTP_302_FOUND)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    resp = UserResponse.model_validate(current_user)
    member_id = (
        db.query(Member.id).filter_by(user_id=current_user.id).scalar()
    )
    resp.member_id = member_id
    resp.has_profile = member_id is not None
    return resp


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[UserResponse]:
    # Left-join the member profile so backfilled accounts with no username or
    # Discord handle still surface a human name in the admin list.
    rows = (
        db.query(User, Member.real_name)
        .outerjoin(Member, Member.user_id == User.id)
        .order_by(User.id)
        .all()
    )
    result: list[UserResponse] = []
    for user, real_name in rows:
        resp = UserResponse.model_validate(user)
        resp.member_name = real_name
        result.append(resp)
    return result


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


@router.delete(
    "/pending-links/{discord_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_pending_link(
    discord_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    # Dismiss a queued Discord login without linking it. The person can log
    # in again to re-queue, so this is a low-stakes cleanup action.
    row = (
        db.query(PendingDiscordLink).filter_by(discord_id=discord_id).one_or_none()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pending link not found"
        )
    db.delete(row)
    db.commit()


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


@router.get("/discord/guild", response_model=GuildConfigResponse)
def get_discord_guild(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> GuildConfigResponse:
    return GuildConfigResponse(guild_id=get_str(db, DISCORD_GUILD_ID_KEY))


@router.put("/discord/guild", response_model=GuildConfigResponse)
def update_discord_guild(
    payload: GuildConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> GuildConfigResponse:
    set_str(db, DISCORD_GUILD_ID_KEY, payload.guild_id)
    db.commit()
    return GuildConfigResponse(guild_id=payload.guild_id)


# One-time member-registration links. 48h, single-use. Shared to a new
# member as /api/auth/discord/register?token=<token>.
INVITE_TTL = timedelta(hours=48)


@router.post(
    "/registration-invites",
    response_model=RegistrationInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_registration_invite(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> RegistrationInvite:
    now = datetime.now(UTC)
    invite = RegistrationInvite(
        token=secrets.token_urlsafe(32),
        created_by_user_id=admin.id,
        created_at=now,
        expires_at=now + INVITE_TTL,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


@router.get("/registration-invites", response_model=list[RegistrationInviteResponse])
def list_registration_invites(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[RegistrationInvite]:
    return (
        db.query(RegistrationInvite)
        .order_by(RegistrationInvite.created_at.desc())
        .all()
    )


@router.delete(
    "/registration-invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_registration_invite(
    invite_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    # Revoke an invite. Deleting a used invite only removes the record; the
    # member account it created is untouched.
    row = db.query(RegistrationInvite).filter_by(id=invite_id).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )
    db.delete(row)
    db.commit()


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
