from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, PendingDiscordLink, User, UserRole


@pytest.fixture
def client(db_session):
    db_session.add(
        User(
            username="admin",
            password_hash=hash_password("admin-pw"),
            role=UserRole.ADMIN,
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


def _login_admin(client):
    assert (
        client.post("/api/auth/login", json={"password": "admin-pw"}).status_code
        == 200
    )


def _seed_member_account(db, real_name="王小明"):
    u = User(role=UserRole.MEMBER)
    db.add(u)
    db.flush()
    m = Member(graduation_year=2024, real_name=real_name, institution="X", user_id=u.id)
    db.add(m)
    db.commit()
    return u, m


def _seed_pending(db, discord_id="P1"):
    row = PendingDiscordLink(
        discord_id=discord_id,
        discord_username="ghost",
        discord_global_name="Ghost",
        first_seen_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    return row


# ---------- list pending links ----------


def test_list_pending_links_requires_admin(client):
    assert client.get("/api/auth/pending-links").status_code == 401


def test_list_pending_links_returns_rows(client, db_session):
    _seed_pending(db_session, "P1")
    _login_admin(client)

    r = client.get("/api/auth/pending-links")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["discord_id"] == "P1"
    assert body[0]["discord_username"] == "ghost"
