import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole


@pytest.fixture
def ctx(db_session):
    admin = User(
        username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN
    )
    viewer = User(
        username="viewer", password_hash=hash_password("viewer-pw"), role=UserRole.VIEWER
    )
    mem = User(
        username="mem", password_hash=hash_password("mem-pw"), role=UserRole.MEMBER
    )
    np = User(
        username="np", password_hash=hash_password("np-pw"), role=UserRole.MEMBER
    )
    db_session.add_all([admin, viewer, mem, np])
    db_session.flush()
    mem_member = Member(
        graduation_year=2024, real_name="我本人", institution="X", user_id=mem.id
    )
    other = Member(graduation_year=2024, real_name="別人", institution="Y")
    db_session.add_all([mem_member, other])
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    def login(pw):
        assert client.post("/api/auth/login", json={"password": pw}).status_code == 200

    try:
        yield client, login, {"mem_member": mem_member.id, "other": other.id}
    finally:
        client.close()
        app.dependency_overrides.clear()


_BASE = {"job_year": 2025, "job_month": 6, "company": "Acme", "kind": "internship"}


def _payload(**kw):
    p = {**_BASE, "experience_md": "hi"}
    p.update(kw)
    return p


# ---------- create: admin ----------


def test_admin_create_with_subject_is_accepted(ctx, db_session):
    client, login, ids = ctx
    login("admin-pw")
    r = client.post(
        "/api/jobs", json=_payload(subject_member_id=ids["other"], is_anonymous=False)
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "accepted"
    assert body["display_name"] == "別人"
    assert body["subject_member_id"] == ids["other"]


def test_admin_create_with_real_name_fallback(ctx):
    client, login, _ = ctx
    login("admin-pw")
    r = client.post("/api/jobs", json=_payload(real_name="Carol"))
    assert r.status_code == 201
    assert r.json()["display_name"] == "Carol"
    assert r.json()["status"] == "accepted"


def test_admin_create_with_unknown_subject_404(ctx):
    client, login, _ = ctx
    login("admin-pw")
    r = client.post("/api/jobs", json=_payload(subject_member_id=99999))
    assert r.status_code == 404


# ---------- create: member ----------


def test_member_create_is_pending_and_subject_is_self(ctx, db_session):
    client, login, ids = ctx
    login("mem-pw")
    # Even if a member tries to attribute the post to someone else, it's
    # forced back to themselves.
    r = client.post(
        "/api/jobs", json=_payload(subject_member_id=ids["other"], real_name="冒充")
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["subject_member_id"] == ids["mem_member"]
    assert body["display_name"] == "我本人"  # owner sees their own name
    assert body["can_edit"] is True


def test_member_create_anonymous(ctx):
    client, login, _ = ctx
    login("mem-pw")
    r = client.post("/api/jobs", json=_payload(is_anonymous=True))
    assert r.status_code == 201
    assert r.json()["is_anonymous"] is True


def test_member_without_profile_cannot_create(ctx):
    client, login, _ = ctx
    login("np-pw")
    r = client.post("/api/jobs", json=_payload())
    assert r.status_code == 403


def test_viewer_cannot_create(ctx):
    client, login, _ = ctx
    login("viewer-pw")
    r = client.post("/api/jobs", json=_payload())
    assert r.status_code == 403
