import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import User, UserRole

TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000000500010d0a2db40000000049454e44"
    "ae426082"
)


@pytest.fixture
def client(db_session):
    db_session.add_all([
        User(username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN),
        User(username="viewer", password_hash=hash_password("viewer-pw"), role=UserRole.VIEWER),
    ])
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _login_admin(client):
    assert client.post("/api/auth/login", json={"password": "admin-pw"}).status_code == 200


def _login_viewer(client):
    assert client.post("/api/auth/login", json={"password": "viewer-pw"}).status_code == 200


# ---------- GET ----------


def test_get_login_logo_anonymous_404_when_unset(client):
    r = client.get("/api/settings/login_logo/image")
    assert r.status_code == 404


def test_get_unknown_key_404(client):
    r = client.get("/api/settings/bogus/image")
    assert r.status_code == 404


def test_get_login_logo_anonymous_200_after_upload(client):
    _login_admin(client)
    up = client.post(
        "/api/settings/login_logo/image",
        files={"file": ("logo.png", TINY_PNG, "image/png")},
    )
    assert up.status_code == 200

    # New TestClient-like flow: anonymous fetch
    client.cookies.clear()
    r = client.get("/api/settings/login_logo/image")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == TINY_PNG
    assert "etag" in {k.lower() for k in r.headers}


# ---------- POST ----------


def test_upload_login_logo_admin_success(client):
    _login_admin(client)
    r = client.post(
        "/api/settings/login_logo/image",
        files={"file": ("logo.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["key"] == "login_logo"
    assert body["content_type"] == "image/png"
    assert body["size"] == len(TINY_PNG)


def test_upload_overwrites_previous(client):
    _login_admin(client)
    client.post(
        "/api/settings/login_logo/image",
        files={"file": ("a.png", TINY_PNG, "image/png")},
    )
    other = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    r = client.post(
        "/api/settings/login_logo/image",
        files={"file": ("b.png", other, "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["size"] == len(other)


def test_upload_login_logo_viewer_forbidden(client):
    _login_viewer(client)
    r = client.post(
        "/api/settings/login_logo/image",
        files={"file": ("logo.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 403


def test_upload_login_logo_unauthenticated(client):
    r = client.post(
        "/api/settings/login_logo/image",
        files={"file": ("logo.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 401


def test_upload_unknown_key_404(client):
    _login_admin(client)
    r = client.post(
        "/api/settings/bogus/image",
        files={"file": ("logo.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 404


def test_upload_rejects_unsupported_mime(client):
    _login_admin(client)
    r = client.post(
        "/api/settings/login_logo/image",
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert r.status_code == 415


def test_upload_rejects_oversized(client):
    _login_admin(client)
    too_big = b"\x89PNG" + b"\x00" * (2 * 1024 * 1024 + 1)
    r = client.post(
        "/api/settings/login_logo/image",
        files={"file": ("big.png", too_big, "image/png")},
    )
    assert r.status_code == 413


# ---------- DELETE ----------


def test_delete_login_logo_admin(client):
    _login_admin(client)
    client.post(
        "/api/settings/login_logo/image",
        files={"file": ("logo.png", TINY_PNG, "image/png")},
    )

    r = client.delete("/api/settings/login_logo/image")
    assert r.status_code == 204

    client.cookies.clear()
    assert client.get("/api/settings/login_logo/image").status_code == 404


def test_delete_when_unset_is_idempotent_204(client):
    _login_admin(client)
    r = client.delete("/api/settings/login_logo/image")
    assert r.status_code == 204


def test_delete_login_logo_viewer_forbidden(client):
    _login_viewer(client)
    r = client.delete("/api/settings/login_logo/image")
    assert r.status_code == 403


def test_delete_login_logo_unauthenticated(client):
    r = client.delete("/api/settings/login_logo/image")
    assert r.status_code == 401
