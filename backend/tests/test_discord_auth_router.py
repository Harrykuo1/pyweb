from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.core import discord_oauth
from app.core.config import settings
from app.core.runtime_config import DISCORD_GUILD_ID_KEY
from app.database import get_db
from app.main import app
from app.models import AppConfig, User, UserRole


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "discord_client_id", "cid")
    monkeypatch.setattr(settings, "discord_client_secret", "secret")
    monkeypatch.setattr(
        settings,
        "discord_redirect_uri",
        "http://localhost:8081/api/auth/discord/callback",
    )


@pytest.fixture
def client(db_session, configured):
    # A member account already linked to a Discord id, plus a configured
    # guild. This is the "already linked" world Phase 2 handles; the
    # first-login bridge that sets discord_id is Phase 3.
    db_session.add(User(role=UserRole.MEMBER, discord_id="D123"))
    db_session.add(AppConfig(key=DISCORD_GUILD_ID_KEY, value="G1"))
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _start_and_get_state(client) -> str:
    r = client.get("/api/auth/discord/login", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert urlparse(loc).netloc == "discord.com"
    return parse_qs(urlparse(loc).query)["state"][0]


def _patch_flow(monkeypatch, *, identity_id="D123", is_member=True):
    monkeypatch.setattr(discord_oauth, "exchange_code", lambda code: "tok")
    monkeypatch.setattr(
        discord_oauth,
        "fetch_identity",
        lambda tok: discord_oauth.DiscordIdentity(
            id=identity_id, username="harry", global_name="Harry"
        ),
    )
    monkeypatch.setattr(discord_oauth, "is_guild_member", lambda tok, gid: is_member)


def test_login_redirects_to_discord_with_client_id_and_state(client):
    r = client.get("/api/auth/discord/login", follow_redirects=False)
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["client_id"] == ["cid"]
    assert "state" in q


def test_login_400_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "discord_client_id", "")
    r = client.get("/api/auth/discord/login", follow_redirects=False)
    assert r.status_code == 400


def test_callback_links_existing_user_and_establishes_session(client, monkeypatch):
    _patch_flow(monkeypatch, identity_id="D123", is_member=True)
    state = _start_and_get_state(client)

    r = client.get(
        f"/api/auth/discord/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "member"


def test_callback_blocks_non_guild_member(client, monkeypatch):
    _patch_flow(monkeypatch, identity_id="D123", is_member=False)
    state = _start_and_get_state(client)

    r = client.get(
        f"/api/auth/discord/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "error=not_member" in r.headers["location"]
    assert client.get("/api/auth/me").status_code == 401


def test_callback_unlinked_identity_is_turned_away(client, monkeypatch):
    _patch_flow(monkeypatch, identity_id="UNKNOWN", is_member=True)
    state = _start_and_get_state(client)

    r = client.get(
        f"/api/auth/discord/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "error=not_linked" in r.headers["location"]
    assert client.get("/api/auth/me").status_code == 401


def test_callback_rejects_state_mismatch(client, monkeypatch):
    _patch_flow(monkeypatch)
    # No prior /login, so the session has no stored state.
    r = client.get(
        "/api/auth/discord/callback?code=abc&state=forged",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "error=state_mismatch" in r.headers["location"]
    assert client.get("/api/auth/me").status_code == 401


def test_callback_first_login_links_precreated_account(client, db_session, monkeypatch):
    # A pre-created account waiting on its resume handle (no discord_id yet).
    from app.models import Member

    u = User(role=UserRole.MEMBER, pending_discord_username="harry")
    db_session.add(u)
    db_session.flush()
    db_session.add(
        Member(graduation_year=2024, real_name="H", institution="X", user_id=u.id)
    )
    db_session.commit()

    _patch_flow(monkeypatch, identity_id="NEWID", is_member=True)
    # fetch_identity must return username "harry" to match the pending handle
    monkeypatch.setattr(
        discord_oauth,
        "fetch_identity",
        lambda tok: discord_oauth.DiscordIdentity(
            id="NEWID", username="harry", global_name="H"
        ),
    )
    state = _start_and_get_state(client)

    r = client.get(
        f"/api/auth/discord/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/"
    # discord_id got backfilled and the account can now log in by id.
    db_session.expire_all()
    linked = db_session.query(User).filter_by(id=u.id).one()
    assert linked.discord_id == "NEWID"
    assert linked.pending_discord_username is None


def test_callback_unmatched_first_login_queues_pending(client, db_session, monkeypatch):
    _patch_flow(monkeypatch, identity_id="Z9", is_member=True)
    monkeypatch.setattr(
        discord_oauth,
        "fetch_identity",
        lambda tok: discord_oauth.DiscordIdentity(
            id="Z9", username="nobody", global_name=None
        ),
    )
    state = _start_and_get_state(client)

    r = client.get(
        f"/api/auth/discord/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "error=not_linked" in r.headers["location"]
    from app.models import PendingDiscordLink

    assert db_session.query(PendingDiscordLink).filter_by(discord_id="Z9").count() == 1


def test_callback_registers_new_member_via_invite(client, db_session, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from urllib.parse import parse_qs, urlparse

    from app.models import RegistrationInvite

    now = datetime.now(UTC)
    db_session.add(
        RegistrationInvite(
            token="inv1", created_at=now, expires_at=now + timedelta(hours=1)
        )
    )
    db_session.commit()

    _patch_flow(monkeypatch, identity_id="FRESH", is_member=True)
    monkeypatch.setattr(
        discord_oauth,
        "fetch_identity",
        lambda tok: discord_oauth.DiscordIdentity(
            id="FRESH", username="fresh", global_name="Fresh"
        ),
    )
    # Start via the register endpoint so the invite token lands in session.
    r0 = client.get(
        "/api/auth/discord/register?token=inv1", follow_redirects=False
    )
    state = parse_qs(urlparse(r0.headers["location"]).query)["state"][0]

    r = client.get(
        f"/api/auth/discord/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/register/profile"

    created = db_session.query(User).filter_by(discord_id="FRESH").one()
    assert created.role.value == "member"
    assert client.get("/api/auth/me").status_code == 200
