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


def test_login_success_returns_user_and_sets_cookie(client):
    r = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pw"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert "id" in body
    assert "password_hash" not in body
    assert "session" in r.cookies


def test_login_wrong_password_returns_401(client):
    r = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "WRONG"},
    )

    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid username or password"


def test_login_unknown_user_returns_401(client):
    r = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "x"},
    )

    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid username or password"


def test_login_rejects_empty_username(client):
    r = client.post(
        "/api/auth/login",
        json={"username": "", "password": "x"},
    )

    assert r.status_code == 422


def test_me_without_login_returns_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_after_login_returns_current_user(client):
    client.post(
        "/api/auth/login",
        json={"username": "viewer", "password": "viewer-pw"},
    )
    r = client.get("/api/auth/me")

    assert r.status_code == 200
    assert r.json()["username"] == "viewer"
    assert r.json()["role"] == "viewer"


def test_logout_clears_session(client):
    client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pw"},
    )
    assert client.get("/api/auth/me").status_code == 200

    r = client.post("/api/auth/logout")
    assert r.status_code == 204

    assert client.get("/api/auth/me").status_code == 401


def test_full_session_lifecycle(client):
    assert client.get("/api/auth/me").status_code == 401

    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pw"},
    )
    assert login.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204

    assert client.get("/api/auth/me").status_code == 401
