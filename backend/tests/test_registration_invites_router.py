from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import RegistrationInvite, User, UserRole


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


def _configure(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "discord_client_id", "cid")
    monkeypatch.setattr(settings, "discord_client_secret", "secret")
    monkeypatch.setattr(
        settings,
        "discord_redirect_uri",
        "http://localhost:8081/api/auth/discord/callback",
    )


def test_generate_invite_requires_admin(client):
    assert client.post("/api/auth/registration-invites").status_code == 401


def test_generate_invite_creates_single_use_48h_token(client, db_session):
    _login_admin(client)
    before = datetime.now(UTC)

    r = client.post("/api/auth/registration-invites")
    assert r.status_code == 201
    body = r.json()
    assert body["token"]
    assert body["used_at"] is None

    row = db_session.query(RegistrationInvite).filter_by(token=body["token"]).one()
    assert row.used_at is None
    delta = row.expires_at.replace(tzinfo=UTC) - before
    assert timedelta(hours=47, minutes=59) < delta < timedelta(hours=48, minutes=1)


def test_list_invites_returns_created_rows(client, db_session):
    _login_admin(client)
    client.post("/api/auth/registration-invites")

    r = client.get("/api/auth/registration-invites")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_list_invites_requires_admin(client):
    assert client.get("/api/auth/registration-invites").status_code == 401


def test_register_start_redirects_to_discord_for_valid_token(
    client, db_session, monkeypatch
):
    _configure(monkeypatch)
    _login_admin(client)
    token = client.post("/api/auth/registration-invites").json()["token"]
    client.post("/api/auth/logout")

    r = client.get(
        f"/api/auth/discord/register?token={token}", follow_redirects=False
    )
    assert r.status_code == 302
    assert "discord.com" in r.headers["location"]


def test_register_start_rejects_unknown_token(client, monkeypatch):
    _configure(monkeypatch)
    r = client.get(
        "/api/auth/discord/register?token=nope", follow_redirects=False
    )
    assert r.status_code == 302
    assert "error=invalid_invite" in r.headers["location"]


def test_register_start_rejects_used_token(client, db_session, monkeypatch):
    _configure(monkeypatch)
    _login_admin(client)
    token = client.post("/api/auth/registration-invites").json()["token"]
    row = db_session.query(RegistrationInvite).filter_by(token=token).one()
    row.used_at = datetime.now(UTC)
    db_session.commit()
    client.post("/api/auth/logout")

    r = client.get(
        f"/api/auth/discord/register?token={token}", follow_redirects=False
    )
    assert "error=invalid_invite" in r.headers["location"]
