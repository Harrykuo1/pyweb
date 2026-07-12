import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.core.deps import (
    admin_password_account,
    get_current_user,
    require_admin,
    require_admin_password,
    require_member,
    verify_admin_password,
)
from app.core.security import hash_password
from app.database import get_db
from app.models import User, UserRole


def _build_app(db_session, *, seed_users: list[User] | None = None) -> FastAPI:
    """Minimal app exposing endpoints that exercise the dependencies.

    Uses the in-memory db_session via dependency override so no real
    database file is touched.
    """
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-key")

    if seed_users:
        for u in seed_users:
            db_session.add(u)
        db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    @app.post("/test/_login_as/{user_id}")
    def login_as(user_id: int, request: Request):
        request.session["user_id"] = user_id
        # Mirror what the real login does: stamp the user's password
        # version so get_current_user's stale-session check passes.
        user = db_session.query(User).filter_by(id=user_id).one_or_none()
        if user is not None:
            request.session["password_version"] = user.password_version
        return {"ok": True}

    @app.get("/test/me")
    def me(user: User = Depends(get_current_user)):
        return {"id": user.id, "username": user.username, "role": user.role.value}

    @app.get("/test/admin-only")
    def admin_only(user: User = Depends(require_admin)):
        return {"id": user.id}

    @app.get("/test/member-only")
    def member_only(user: User = Depends(require_member)):
        return {"id": user.id}

    return app


def test_get_current_user_returns_401_when_no_session(db_session):
    app = _build_app(db_session)
    client = TestClient(app)

    r = client.get("/test/me")
    assert r.status_code == 401
    assert r.json()["detail"] == "Not authenticated"


def test_get_current_user_returns_user_when_session_valid(db_session):
    seed = [User(id=1, username="alice", password_hash="h", role=UserRole.VIEWER)]
    app = _build_app(db_session, seed_users=seed)
    client = TestClient(app)

    client.post("/test/_login_as/1")
    r = client.get("/test/me")

    assert r.status_code == 200
    assert r.json() == {"id": 1, "username": "alice", "role": "viewer"}


def test_get_current_user_clears_session_when_user_deleted(db_session):
    seed = [User(id=2, username="ghost", password_hash="h", role=UserRole.VIEWER)]
    app = _build_app(db_session, seed_users=seed)
    client = TestClient(app)

    client.post("/test/_login_as/2")
    db_session.query(User).filter_by(id=2).delete()
    db_session.commit()

    r = client.get("/test/me")
    assert r.status_code == 401
    assert "no longer exists" in r.json()["detail"]

    r2 = client.get("/test/me")
    assert r2.status_code == 401


def test_require_admin_allows_admin(db_session):
    seed = [User(id=10, username="admin", password_hash="h", role=UserRole.ADMIN)]
    app = _build_app(db_session, seed_users=seed)
    client = TestClient(app)

    client.post("/test/_login_as/10")
    r = client.get("/test/admin-only")

    assert r.status_code == 200
    assert r.json() == {"id": 10}


def test_require_admin_rejects_viewer(db_session):
    seed = [User(id=11, username="viewer", password_hash="h", role=UserRole.VIEWER)]
    app = _build_app(db_session, seed_users=seed)
    client = TestClient(app)

    client.post("/test/_login_as/11")
    r = client.get("/test/admin-only")

    assert r.status_code == 403
    assert r.json()["detail"] == "Admin role required"


def test_require_admin_rejects_unauthenticated(db_session):
    app = _build_app(db_session)
    client = TestClient(app)

    r = client.get("/test/admin-only")
    assert r.status_code == 401


def test_require_member_allows_member(db_session):
    seed = [User(id=20, username="m", password_hash="h", role=UserRole.MEMBER)]
    app = _build_app(db_session, seed_users=seed)
    client = TestClient(app)

    client.post("/test/_login_as/20")
    r = client.get("/test/member-only")

    assert r.status_code == 200
    assert r.json() == {"id": 20}


def test_require_member_allows_admin(db_session):
    seed = [User(id=21, username="a", password_hash="h", role=UserRole.ADMIN)]
    app = _build_app(db_session, seed_users=seed)
    client = TestClient(app)

    client.post("/test/_login_as/21")
    assert client.get("/test/member-only").status_code == 200


def test_require_member_rejects_viewer(db_session):
    seed = [User(id=22, username="v", password_hash="h", role=UserRole.VIEWER)]
    app = _build_app(db_session, seed_users=seed)
    client = TestClient(app)

    client.post("/test/_login_as/22")
    r = client.get("/test/member-only")

    assert r.status_code == 403
    assert r.json()["detail"] == "Member role required"


def test_require_member_rejects_unauthenticated(db_session):
    app = _build_app(db_session)
    client = TestClient(app)

    assert client.get("/test/member-only").status_code == 401


def test_get_current_user_rejects_suspended_account(db_session):
    seed = [
        User(
            id=30,
            role=UserRole.MEMBER,
            discord_id="s1",
            discord_username="s",
            is_active=False,
        )
    ]
    app = _build_app(db_session, seed_users=seed)
    client = TestClient(app)

    client.post("/test/_login_as/30")
    r = client.get("/test/me")

    assert r.status_code == 401
    assert r.json()["detail"] == "Account suspended"

    # Session was cleared, so a second call is still 401.
    assert client.get("/test/me").status_code == 401


def test_get_current_user_allows_active_account(db_session):
    seed = [
        User(
            id=31,
            role=UserRole.MEMBER,
            discord_id="a1",
            discord_username="a",
            is_active=True,
        )
    ]
    app = _build_app(db_session, seed_users=seed)
    client = TestClient(app)

    client.post("/test/_login_as/31")
    assert client.get("/test/me").status_code == 200


def test_get_current_user_evicts_session_after_password_version_bump(db_session):
    seed = [User(id=3, username="rot", password_hash="h", role=UserRole.VIEWER)]
    app = _build_app(db_session, seed_users=seed)
    client = TestClient(app)

    client.post("/test/_login_as/3")
    assert client.get("/test/me").status_code == 200  # valid at version 1

    # Rotate the password version out from under the live session, exactly
    # like reset_password / update_password do on the real path.
    user = db_session.query(User).filter_by(id=3).one()
    user.password_version += 1
    db_session.commit()

    r = client.get("/test/me")
    assert r.status_code == 401
    assert r.json()["detail"] == "Session expired due to password change"

    # Dependency cleared the cookie, so a second call is still 401.
    assert client.get("/test/me").status_code == 401


# ---------- admin-password confirmation (shared destructive-action gate) ----------


def _seed(db_session, *users: User) -> None:
    db_session.add_all(users)
    db_session.commit()


def test_admin_password_account_is_lowest_id_password_admin(db_session):
    # Two password admins plus a Discord admin (no password). The break-glass
    # account is the lowest-id ADMIN that still has a password.
    _seed(
        db_session,
        User(
            id=1,
            username="a1",
            password_hash=hash_password("first"),
            role=UserRole.ADMIN,
        ),
        User(
            id=2,
            username="a2",
            password_hash=hash_password("second"),
            role=UserRole.ADMIN,
        ),
        User(id=3, role=UserRole.ADMIN, discord_id="d1", discord_username="d"),
    )
    account = admin_password_account(db_session)
    assert account is not None
    assert account.id == 1


def test_admin_password_account_ignores_discord_admin(db_session):
    # A Discord-linked admin has no password_hash, so it can never be the
    # break-glass confirmation account.
    _seed(
        db_session,
        User(id=5, role=UserRole.ADMIN, discord_id="d2", discord_username="d2"),
    )
    assert admin_password_account(db_session) is None


def test_verify_admin_password_checks_the_account_not_the_actor(db_session):
    # The confirmation credential is the admin ACCOUNT's password. A second
    # admin's own password must NOT pass — only the break-glass one's does.
    _seed(
        db_session,
        User(
            id=1,
            username="a1",
            password_hash=hash_password("break-glass"),
            role=UserRole.ADMIN,
        ),
        User(
            id=2,
            username="a2",
            password_hash=hash_password("other-admin"),
            role=UserRole.ADMIN,
        ),
    )
    assert verify_admin_password(db_session, "break-glass") is True
    assert verify_admin_password(db_session, "other-admin") is False
    assert verify_admin_password(db_session, "wrong") is False


def test_verify_admin_password_false_when_no_password_admin(db_session):
    _seed(
        db_session,
        User(id=9, role=UserRole.ADMIN, discord_id="d3", discord_username="d3"),
    )
    assert verify_admin_password(db_session, "anything") is False


def test_require_admin_password_raises_422_on_mismatch(db_session):
    _seed(
        db_session,
        User(
            id=1,
            username="a1",
            password_hash=hash_password("correct"),
            role=UserRole.ADMIN,
        ),
    )
    with pytest.raises(HTTPException) as exc:
        require_admin_password(db_session, "wrong")
    assert exc.value.status_code == 422


def test_require_admin_password_passes_on_match(db_session):
    _seed(
        db_session,
        User(
            id=1,
            username="a1",
            password_hash=hash_password("correct"),
            role=UserRole.ADMIN,
        ),
    )
    # No exception == success.
    require_admin_password(db_session, "correct")
