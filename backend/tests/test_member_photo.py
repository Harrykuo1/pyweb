from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole

# Tiny valid PNG (1x1 transparent pixel) to keep payloads cheap.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000000500010d0a2db40000000049454e44"
    "ae426082"
)


@pytest.fixture
def client_factory(db_session):
    db_session.add_all([
        User(username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN),
        User(username="viewer", password_hash=hash_password("viewer-pw"), role=UserRole.VIEWER),
    ])
    db_session.add(
        Member(
            id=1,
            graduation_year=2024,
            real_name="Alice",
            institution="SWE",
            joined_at=datetime.now(timezone.utc),
        )
    )
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


# ---------- upload ----------

def test_upload_photo_admin(client_factory, db_session):
    client, login_as = client_factory
    login_as("admin")

    r = client.post(
        "/api/members/1/photo",
        files={"file": ("a.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_photo"] is True
    assert body["photo_updated_at"] is not None

    member = db_session.query(Member).filter_by(id=1).one()
    assert member.photo == TINY_PNG
    assert member.photo_content_type == "image/png"
    assert member.photo_updated_at is not None


def test_upload_photo_bumps_timestamp_on_each_upload(client_factory, db_session):
    client, login_as = client_factory
    login_as("admin")

    r1 = client.post(
        "/api/members/1/photo", files={"file": ("a.png", TINY_PNG, "image/png")}
    )
    first = r1.json()["photo_updated_at"]
    assert first is not None

    r2 = client.post(
        "/api/members/1/photo", files={"file": ("a.png", TINY_PNG, "image/png")}
    )
    second = r2.json()["photo_updated_at"]
    assert second is not None
    assert second >= first


def test_upload_photo_viewer_403(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.post(
        "/api/members/1/photo",
        files={"file": ("a.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 403


def test_upload_photo_unauth_401(client_factory):
    client, _ = client_factory
    r = client.post(
        "/api/members/1/photo",
        files={"file": ("a.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 401


def test_upload_photo_rejects_unsupported_mime(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/members/1/photo",
        files={"file": ("a.gif", b"GIF89a", "image/gif")},
    )
    assert r.status_code == 415


def test_upload_photo_rejects_oversized(client_factory):
    client, login_as = client_factory
    login_as("admin")
    big = b"\x00" * (5 * 1024 * 1024 + 1)
    r = client.post(
        "/api/members/1/photo",
        files={"file": ("big.png", big, "image/png")},
    )
    assert r.status_code == 413


def test_upload_photo_404(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/members/9999/photo",
        files={"file": ("a.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 404


# ---------- get ----------

def test_get_photo_returns_bytes_with_content_type(client_factory, db_session):
    client, login_as = client_factory
    member = db_session.query(Member).filter_by(id=1).one()
    member.photo = TINY_PNG
    member.photo_content_type = "image/png"
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/members/1/photo")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == TINY_PNG


def test_get_photo_response_uses_immutable_cache_header(client_factory, db_session):
    # Photo URLs carry a ?v=<photo_updated_at> stamp, so the bytes at a
    # given URL never change. Tell the browser to cache forever and
    # skip conditional revalidation — admin replacing the photo bumps
    # photo_updated_at, which changes the URL.
    client, login_as = client_factory
    member = db_session.query(Member).filter_by(id=1).one()
    member.photo = TINY_PNG
    member.photo_content_type = "image/png"
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/members/1/photo")
    assert r.status_code == 200
    cache_control = r.headers.get("cache-control", "")
    assert "private" in cache_control
    assert "max-age=31536000" in cache_control
    assert "immutable" in cache_control


def test_get_photo_404_when_missing(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/members/1/photo")
    assert r.status_code == 404


def test_get_photo_unauth_401(client_factory):
    client, _ = client_factory
    r = client.get("/api/members/1/photo")
    assert r.status_code == 401


# ---------- delete ----------

def test_delete_photo_admin(client_factory, db_session):
    client, login_as = client_factory
    member = db_session.query(Member).filter_by(id=1).one()
    member.photo = TINY_PNG
    member.photo_content_type = "image/png"
    member.photo_updated_at = datetime.now(timezone.utc)
    db_session.commit()
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/photo", json={"password": "admin-pw"},
    )
    assert r.status_code == 204

    db_session.refresh(member)
    assert member.photo is None
    assert member.photo_content_type is None
    assert member.photo_updated_at is None


def test_delete_photo_wrong_password_returns_422(client_factory, db_session):
    # See members router helper for why this is 422 instead of 401.
    client, login_as = client_factory
    member = db_session.query(Member).filter_by(id=1).one()
    member.photo = TINY_PNG
    member.photo_content_type = "image/png"
    db_session.commit()
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/photo", json={"password": "wrong-pw"},
    )
    assert r.status_code == 422

    db_session.refresh(member)
    assert member.photo == TINY_PNG


def test_delete_photo_missing_password_422(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.delete("/api/members/1/photo")
    assert r.status_code == 422


def test_delete_photo_viewer_403(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.request(
        "DELETE", "/api/members/1/photo", json={"password": "viewer-pw"},
    )
    assert r.status_code == 403


def test_delete_photo_404(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.request(
        "DELETE", "/api/members/9999/photo", json={"password": "admin-pw"},
    )
    assert r.status_code == 404
