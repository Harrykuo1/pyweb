from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole


@pytest.fixture
def client_factory(db_session):
    """Returns (client, login_as) where login_as logs in as one of admin/viewer."""
    db_session.add_all([
        User(username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN),
        User(username="viewer", password_hash=hash_password("viewer-pw"), role=UserRole.VIEWER),
    ])
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    def login_as(role):
        creds = {"admin": ("admin", "admin-pw"), "viewer": ("viewer", "viewer-pw")}[role]
        r = client.post("/api/auth/login", json={"username": creds[0], "password": creds[1]})
        assert r.status_code == 200, r.text

    try:
        yield client, login_as
    finally:
        client.close()
        app.dependency_overrides.clear()


def _seed_members(db_session, count=3):
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(count):
        db_session.add(
            Member(
                graduation_year=2020 + i,
                real_name=f"member-{i}",
                institution=f"role-{i}",
                joined_at=base.replace(month=1 + i),
            )
        )
    db_session.commit()


# ---------- list ----------

def test_list_members_requires_auth(client_factory):
    client, _ = client_factory
    r = client.get("/api/members")
    assert r.status_code == 401


def test_list_members_default_order_asc(client_factory, db_session):
    client, login_as = client_factory
    _seed_members(db_session)
    login_as("viewer")

    r = client.get("/api/members")
    assert r.status_code == 200
    names = [m["real_name"] for m in r.json()]
    assert names == ["member-0", "member-1", "member-2"]


def test_list_members_desc_order(client_factory, db_session):
    client, login_as = client_factory
    _seed_members(db_session)
    login_as("viewer")

    r = client.get("/api/members?order=desc")
    assert r.status_code == 200
    names = [m["real_name"] for m in r.json()]
    assert names == ["member-2", "member-1", "member-0"]


def test_list_rejects_invalid_order(client_factory, db_session):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/members?order=garbage")
    assert r.status_code == 422


def test_list_excludes_photo_field(client_factory, db_session):
    client, login_as = client_factory
    db_session.add(
        Member(
            graduation_year=2024,
            real_name="x",
            institution="y",
            photo_path="members/1/photo.png",
            photo_content_type="image/png",
            joined_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/members")
    assert r.status_code == 200
    body = r.json()[0]
    assert "photo" not in body
    assert "photo_path" not in body


# ---------- detail ----------

def test_get_member_returns_404_when_missing(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/members/9999")
    assert r.status_code == 404


def test_get_member_returns_member(client_factory, db_session):
    client, login_as = client_factory
    _seed_members(db_session, count=1)
    login_as("viewer")
    r = client.get("/api/members/1")
    assert r.status_code == 200
    assert r.json()["real_name"] == "member-0"


# ---------- create ----------

def test_create_member_admin_succeeds(client_factory):
    client, login_as = client_factory
    login_as("admin")
    payload = {
        "graduation_year": 2024,
        "real_name": "Alice",
        "institution": "SWE",
        "resume_md": "# resume",
    }
    r = client.post("/api/members", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["real_name"] == "Alice"
    assert body["resume_md"] == "# resume"
    assert body["joined_at"] is not None  # backend defaulted it


def test_create_member_viewer_403(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.post(
        "/api/members",
        json={"graduation_year": 2024, "real_name": "x", "institution": "y"},
    )
    assert r.status_code == 403


def test_create_member_unauth_401(client_factory):
    client, _ = client_factory
    r = client.post(
        "/api/members",
        json={"graduation_year": 2024, "real_name": "x", "institution": "y"},
    )
    assert r.status_code == 401


def test_create_member_validates_payload(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/members",
        json={"graduation_year": 1899, "real_name": "x", "institution": "y"},
    )
    assert r.status_code == 422


def test_create_member_accepts_explicit_joined_at(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/members",
        json={
            "graduation_year": 2020,
            "real_name": "Bob",
            "institution": "MS",
            "joined_at": "2020-09-01",
        },
    )
    assert r.status_code == 201
    assert r.json()["joined_at"].startswith("2020-09-01")


def test_create_member_with_position_round_trips(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/members",
        json={
            "graduation_year": 2024,
            "real_name": "Carol",
            "institution": "NYCU",
            "position": "資工系",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["institution"] == "NYCU"
    assert body["position"] == "資工系"


def test_create_member_without_position_returns_null(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/members",
        json={
            "graduation_year": 2024,
            "real_name": "Dave",
            "institution": "Acme",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["position"] is None


# ---------- update ----------

def test_update_member_admin_partial(client_factory, db_session):
    client, login_as = client_factory
    _seed_members(db_session, count=1)
    login_as("admin")

    r = client.put(
        "/api/members/1",
        json={"institution": "Senior Engineer"},
    )
    assert r.status_code == 200
    assert r.json()["institution"] == "Senior Engineer"
    assert r.json()["real_name"] == "member-0"  # unchanged


def test_update_member_viewer_403(client_factory, db_session):
    client, login_as = client_factory
    _seed_members(db_session, count=1)
    login_as("viewer")
    r = client.put("/api/members/1", json={"real_name": "Hack"})
    assert r.status_code == 403


def test_update_member_404(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.put("/api/members/9999", json={"real_name": "X"})
    assert r.status_code == 404


# ---------- delete ----------

def test_delete_member_admin(client_factory, db_session):
    client, login_as = client_factory
    _seed_members(db_session, count=1)
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1", json={"password": "admin-pw"},
    )
    assert r.status_code == 204

    r2 = client.get("/api/members/1")
    assert r2.status_code == 404


def test_delete_member_wrong_password_returns_422(client_factory, db_session):
    # 422 (not 401) so the frontend's global session-expired interceptor
    # doesn't bounce the user back to /login on a typo'd confirmation.
    client, login_as = client_factory
    _seed_members(db_session, count=1)
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1", json={"password": "not-the-admin-pw"},
    )
    assert r.status_code == 422

    # Member must NOT be deleted when the password check fails.
    r2 = client.get("/api/members/1")
    assert r2.status_code == 200


def test_delete_member_missing_password_422(client_factory, db_session):
    client, login_as = client_factory
    _seed_members(db_session, count=1)
    login_as("admin")

    r = client.delete("/api/members/1")
    assert r.status_code == 422


def test_delete_member_viewer_403(client_factory, db_session):
    client, login_as = client_factory
    _seed_members(db_session, count=1)
    login_as("viewer")
    r = client.request(
        "DELETE", "/api/members/1", json={"password": "viewer-pw"},
    )
    assert r.status_code == 403


def test_delete_member_404(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.request(
        "DELETE", "/api/members/9999", json={"password": "admin-pw"},
    )
    assert r.status_code == 404
