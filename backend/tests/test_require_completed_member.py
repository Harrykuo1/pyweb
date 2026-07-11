from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.core.deps import require_completed_member, require_posting_member
from app.database import get_db
from app.models import Member, User, UserRole


def _build_app(db_session, *, seed_users=None, seed_members=None):
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-key")
    for u in seed_users or []:
        db_session.add(u)
    db_session.commit()
    for m in seed_members or []:
        db_session.add(m)
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    @app.post("/login/{user_id}")
    def login(user_id: int, request: Request):
        request.session["user_id"] = user_id
        u = db_session.query(User).filter_by(id=user_id).one()
        request.session["password_version"] = u.password_version
        return {"ok": True}

    @app.get("/gated")
    def gated(user: User = Depends(require_completed_member)):
        return {"id": user.id}

    @app.get("/posting")
    def posting(user: User = Depends(require_posting_member)):
        return {"id": user.id}

    return app


def test_member_without_profile_blocked(db_session):
    app = _build_app(
        db_session, seed_users=[User(id=1, role=UserRole.MEMBER, discord_id="d1")]
    )
    client = TestClient(app)
    client.post("/login/1")
    r = client.get("/gated")
    assert r.status_code == 403
    assert r.json()["detail"] == "profile_incomplete"


def test_member_with_profile_allowed(db_session):
    app = _build_app(
        db_session,
        seed_users=[User(id=2, role=UserRole.MEMBER, discord_id="d2")],
        seed_members=[
            Member(graduation_year=2024, real_name="A", institution="X", user_id=2)
        ],
    )
    client = TestClient(app)
    client.post("/login/2")
    assert client.get("/gated").status_code == 200


def test_admin_exempt_from_profile_gate(db_session):
    app = _build_app(
        db_session,
        seed_users=[
            User(id=3, username="a", password_hash="h", role=UserRole.ADMIN)
        ],
    )
    client = TestClient(app)
    client.post("/login/3")
    assert client.get("/gated").status_code == 200


def test_viewer_exempt_from_profile_gate(db_session):
    app = _build_app(
        db_session,
        seed_users=[
            User(id=4, username="v", password_hash="h", role=UserRole.VIEWER)
        ],
    )
    client = TestClient(app)
    client.post("/login/4")
    assert client.get("/gated").status_code == 200


def test_unauthenticated_blocked(db_session):
    app = _build_app(db_session)
    client = TestClient(app)
    assert client.get("/gated").status_code == 401


# ---------- require_posting_member (write gate) ----------
# Same profile gate as require_completed_member, but — unlike it — the
# read-only viewer is NOT exempt: viewers must stay unable to post.


def test_posting_member_without_profile_blocked(db_session):
    app = _build_app(
        db_session, seed_users=[User(id=11, role=UserRole.MEMBER, discord_id="p1")]
    )
    client = TestClient(app)
    client.post("/login/11")
    r = client.get("/posting")
    assert r.status_code == 403
    assert r.json()["detail"] == "profile_incomplete"


def test_posting_member_with_profile_allowed(db_session):
    app = _build_app(
        db_session,
        seed_users=[User(id=12, role=UserRole.MEMBER, discord_id="p2")],
        seed_members=[
            Member(graduation_year=2024, real_name="B", institution="Y", user_id=12)
        ],
    )
    client = TestClient(app)
    client.post("/login/12")
    assert client.get("/posting").status_code == 200


def test_posting_admin_allowed(db_session):
    app = _build_app(
        db_session,
        seed_users=[User(id=13, username="pa", password_hash="h", role=UserRole.ADMIN)],
    )
    client = TestClient(app)
    client.post("/login/13")
    assert client.get("/posting").status_code == 200


def test_posting_viewer_blocked(db_session):
    app = _build_app(
        db_session,
        seed_users=[User(id=14, username="pv", password_hash="h", role=UserRole.VIEWER)],
    )
    client = TestClient(app)
    client.post("/login/14")
    assert client.get("/posting").status_code == 403
