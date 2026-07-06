import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole


@pytest.fixture
def client(db_session):
    # A logged-in-able member account with no profile yet (fresh registrant).
    db_session.add(
        User(
            username="m1",
            password_hash=hash_password("m1-pw"),
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


def _login_member(client):
    assert (
        client.post("/api/auth/login", json={"password": "m1-pw"}).status_code == 200
    )


def test_self_create_requires_login(client):
    r = client.post(
        "/api/members/me",
        json={"graduation_year": 2024, "real_name": "新人", "institution": "X"},
    )
    assert r.status_code == 401


def test_self_create_makes_member_linked_to_current_user(client, db_session):
    _login_member(client)
    r = client.post(
        "/api/members/me",
        json={"graduation_year": 2024, "real_name": "新人", "institution": "NYCU"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["real_name"] == "新人"

    user = db_session.query(User).filter_by(username="m1").one()
    member = db_session.query(Member).filter_by(user_id=user.id).one()
    assert member.real_name == "新人"
    assert member.joined_at is not None


def test_self_create_rejects_second_profile(client, db_session):
    _login_member(client)
    payload = {"graduation_year": 2024, "real_name": "新人", "institution": "X"}
    assert client.post("/api/members/me", json=payload).status_code == 201
    assert client.post("/api/members/me", json=payload).status_code == 409
