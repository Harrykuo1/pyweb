import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import User, UserRole


@pytest.fixture
def client(db_session):
    """TestClient wired to the in-memory db_session via dependency override."""
    db_session.add_all([
        User(
            username="admin",
            password_hash=hash_password("admin-pw"),
            role=UserRole.ADMIN,
        ),
        User(
            username="viewer",
            password_hash=hash_password("viewer-pw"),
            role=UserRole.VIEWER,
        ),
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


def test_login_admin_password_returns_admin_user(client):
    r = client.post("/api/auth/login", json={"password": "admin-pw"})

    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert "id" in body
    assert "password_hash" not in body
    assert "session" in r.cookies


def test_login_viewer_password_returns_viewer_user(client):
    r = client.post("/api/auth/login", json={"password": "viewer-pw"})

    assert r.status_code == 200
    assert r.json()["role"] == "viewer"


def test_login_wrong_password_returns_401(client):
    r = client.post("/api/auth/login", json={"password": "WRONG"})

    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid password"


def test_login_rejects_empty_password(client):
    r = client.post("/api/auth/login", json={"password": ""})
    assert r.status_code == 422


def test_login_rejects_missing_password(client):
    r = client.post("/api/auth/login", json={})
    assert r.status_code == 422


def test_me_without_login_returns_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_after_login_returns_current_user(client):
    client.post("/api/auth/login", json={"password": "viewer-pw"})
    r = client.get("/api/auth/me")

    assert r.status_code == 200
    assert r.json()["username"] == "viewer"
    assert r.json()["role"] == "viewer"


def test_logout_clears_session(client):
    client.post("/api/auth/login", json={"password": "admin-pw"})
    assert client.get("/api/auth/me").status_code == 200

    r = client.post("/api/auth/logout")
    assert r.status_code == 204

    assert client.get("/api/auth/me").status_code == 401


def test_full_session_lifecycle(client):
    assert client.get("/api/auth/me").status_code == 401

    login = client.post("/api/auth/login", json={"password": "admin-pw"})
    assert login.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204

    assert client.get("/api/auth/me").status_code == 401


# ---------- admin account management ----------


def _login_admin(client):
    r = client.post("/api/auth/login", json={"password": "admin-pw"})
    assert r.status_code == 200


def _login_viewer(client):
    r = client.post("/api/auth/login", json={"password": "viewer-pw"})
    assert r.status_code == 200


def test_list_users_requires_login(client):
    r = client.get("/api/auth/users")
    assert r.status_code == 401


def test_list_users_forbidden_for_viewer(client):
    _login_viewer(client)
    r = client.get("/api/auth/users")
    assert r.status_code == 403


def test_list_users_returns_both_accounts_for_admin(client):
    _login_admin(client)
    r = client.get("/api/auth/users")

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    roles = {u["role"] for u in body}
    assert roles == {"admin", "viewer"}
    for u in body:
        assert "password_hash" not in u


def test_update_viewer_username_succeeds(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/username",
        json={"username": "watcher"},
    )

    assert r.status_code == 200
    assert r.json()["username"] == "watcher"
    assert r.json()["role"] == "viewer"


def test_update_admin_username_succeeds_and_me_reflects_it(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/admin/username",
        json={"username": "boss"},
    )
    assert r.status_code == 200

    me = client.get("/api/auth/me")
    assert me.json()["username"] == "boss"


def test_update_username_rejects_collision(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/username",
        json={"username": "admin"},
    )
    assert r.status_code == 409


def test_update_username_allows_same_value(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/admin/username",
        json={"username": "admin"},
    )
    assert r.status_code == 200


def test_update_username_rejects_empty(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/username",
        json={"username": ""},
    )
    assert r.status_code == 422


def test_update_username_forbidden_for_viewer(client):
    _login_viewer(client)
    r = client.patch(
        "/api/auth/users/viewer/username",
        json={"username": "watcher"},
    )
    assert r.status_code == 403


def test_update_username_unauthenticated(client):
    r = client.patch(
        "/api/auth/users/viewer/username",
        json={"username": "watcher"},
    )
    assert r.status_code == 401


def test_update_password_succeeds_and_new_password_logs_in(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "admin-pw", "new_password": "fresh-pw"},
    )
    assert r.status_code == 204

    client.post("/api/auth/logout")

    bad = client.post("/api/auth/login", json={"password": "viewer-pw"})
    assert bad.status_code == 401

    ok = client.post("/api/auth/login", json={"password": "fresh-pw"})
    assert ok.status_code == 200
    assert ok.json()["role"] == "viewer"


def test_update_admin_password_then_relogin(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/admin/password",
        json={"current_password": "admin-pw", "new_password": "rotated-pw"},
    )
    assert r.status_code == 204

    client.post("/api/auth/logout")

    ok = client.post("/api/auth/login", json={"password": "rotated-pw"})
    assert ok.status_code == 200
    assert ok.json()["role"] == "admin"


def test_update_password_wrong_current_password(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "WRONG", "new_password": "fresh-pw"},
    )
    assert r.status_code == 401


def test_update_password_collision_with_other_account(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "admin-pw", "new_password": "admin-pw"},
    )
    assert r.status_code == 409


def test_update_password_forbidden_for_viewer(client):
    _login_viewer(client)
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "viewer-pw", "new_password": "x"},
    )
    assert r.status_code == 403


def test_update_password_unauthenticated(client):
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "admin-pw", "new_password": "x"},
    )
    assert r.status_code == 401


def test_update_password_rejects_empty_new_password(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "admin-pw", "new_password": ""},
    )
    assert r.status_code == 422
