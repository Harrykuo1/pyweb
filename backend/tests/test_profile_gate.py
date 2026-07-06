import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import User, UserRole


@pytest.fixture
def client(db_session):
    # A member account WITH a password (so we can log in via the legacy
    # password path) but NO profile yet — a fresh registrant.
    db_session.add(
        User(
            username="newbie",
            password_hash=hash_password("newbie-pw"),
            role=UserRole.MEMBER,
        )
    )
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_member_without_profile_is_gated_from_all_reads(client):
    client.post("/api/auth/login", json={"password": "newbie-pw"})

    assert client.get("/api/members").status_code == 403
    assert client.get("/api/jobs").status_code == 403
    assert client.get("/api/events").status_code == 403

    # /me still works so the frontend can learn to redirect them.
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["has_profile"] is False


def test_member_unlocks_reads_after_creating_profile(client):
    client.post("/api/auth/login", json={"password": "newbie-pw"})

    r = client.post(
        "/api/members/me",
        json={"graduation_year": 2024, "real_name": "新人", "institution": "X"},
    )
    assert r.status_code == 201

    assert client.get("/api/members").status_code == 200
    assert client.get("/api/auth/me").json()["has_profile"] is True
