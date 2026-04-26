from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.core.deps import get_current_user, require_admin
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
        return {"ok": True}

    @app.get("/test/me")
    def me(user: User = Depends(get_current_user)):
        return {"id": user.id, "username": user.username, "role": user.role.value}

    @app.get("/test/admin-only")
    def admin_only(user: User = Depends(require_admin)):
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
