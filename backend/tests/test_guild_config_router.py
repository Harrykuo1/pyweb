import pytest
from fastapi.testclient import TestClient

from app.core.runtime_config import DISCORD_GUILD_ID_KEY
from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import AppConfig, User, UserRole

VALID_GUILD_ID = "1234567890123456789"  # 19-digit snowflake


@pytest.fixture
def client(db_session):
    db_session.add_all(
        [
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
        ]
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


def _login(client, pw):
    assert client.post("/api/auth/login", json={"password": pw}).status_code == 200


def test_get_guild_requires_auth(client):
    assert client.get("/api/auth/discord/guild").status_code == 401


def test_get_guild_forbidden_for_viewer(client):
    _login(client, "viewer-pw")
    assert client.get("/api/auth/discord/guild").status_code == 403


def test_get_guild_returns_empty_when_unset(client):
    _login(client, "admin-pw")
    r = client.get("/api/auth/discord/guild")
    assert r.status_code == 200
    assert r.json() == {"guild_id": ""}


def test_get_guild_returns_configured_value(client, db_session):
    db_session.add(AppConfig(key=DISCORD_GUILD_ID_KEY, value=VALID_GUILD_ID))
    db_session.commit()
    _login(client, "admin-pw")
    r = client.get("/api/auth/discord/guild")
    assert r.status_code == 200
    assert r.json()["guild_id"] == VALID_GUILD_ID


def test_put_guild_requires_auth(client):
    assert (
        client.put(
            "/api/auth/discord/guild", json={"guild_id": VALID_GUILD_ID}
        ).status_code
        == 401
    )


def test_put_guild_forbidden_for_viewer(client):
    _login(client, "viewer-pw")
    assert (
        client.put(
            "/api/auth/discord/guild", json={"guild_id": VALID_GUILD_ID}
        ).status_code
        == 403
    )


def test_put_guild_sets_and_persists(client, db_session):
    _login(client, "admin-pw")
    r = client.put("/api/auth/discord/guild", json={"guild_id": VALID_GUILD_ID})
    assert r.status_code == 200
    assert r.json()["guild_id"] == VALID_GUILD_ID

    row = db_session.query(AppConfig).filter_by(key=DISCORD_GUILD_ID_KEY).one()
    assert row.value == VALID_GUILD_ID
    # A follow-up GET reflects it.
    assert client.get("/api/auth/discord/guild").json()["guild_id"] == VALID_GUILD_ID


def test_put_guild_overwrites_existing(client, db_session):
    db_session.add(AppConfig(key=DISCORD_GUILD_ID_KEY, value="1111111111111111111"))
    db_session.commit()
    _login(client, "admin-pw")

    r = client.put("/api/auth/discord/guild", json={"guild_id": VALID_GUILD_ID})
    assert r.status_code == 200

    rows = db_session.query(AppConfig).filter_by(key=DISCORD_GUILD_ID_KEY).all()
    assert len(rows) == 1  # upsert, not a duplicate insert
    assert rows[0].value == VALID_GUILD_ID


@pytest.mark.parametrize(
    "bad",
    ["", "not-a-number", "12345", "123456789012345678901", "abc123456789012345"],
)
def test_put_guild_rejects_non_snowflake(client, bad):
    _login(client, "admin-pw")
    r = client.put("/api/auth/discord/guild", json={"guild_id": bad})
    assert r.status_code == 422
