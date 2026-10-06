from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import discord_oauth
from app.core.config import settings
from app.models import (
    AppConfig,
    Member,
    MessageEvent,
    PendingDiscordLink,
    User,
    UserRole,
)
from app.routers.members import manually_link_discord
from app.schemas.member_discord import MemberDiscordLinkRequest
from tests import test_members_router as fixtures

client_factory = fixtures.client_factory
DISCORD_ID = "123456789012345678"


def seed_member(db, *, active=True, linked=None):
    account = User(
        role=UserRole.MEMBER,
        pending_discord_username="pending.handle",
        is_active=active,
        discord_id=linked,
    )
    db.add(account)
    db.flush()
    member = Member(
        user_id=account.id,
        real_name="Test member",
        graduation_year=2026,
        institution="Test",
        joined_at=datetime(2020, 1, 1),
        resume_md="keep this",
    )
    db.add(member)
    db.commit()
    return member, account


def url(member):
    return f"/api/members/{member.id}/discord-link"


def test_link_preserves_account_profile_history_and_admin_session(
    client_factory, db_session
):
    client, login = client_factory
    member, account = seed_member(db_session)
    db_session.add(
        MessageEvent(
            guild_id="999",
            message_id="1",
            user_id=DISCORD_ID,
            channel_id="2",
            sent_at=datetime(2026, 1, 1),
            text_length=0,
            attachment_count=0,
        )
    )
    db_session.add(AppConfig(key="discord_guild_id", value="999"))
    db_session.commit()
    login("admin")
    admin_id = client.get("/api/auth/me").json()["id"]
    response = client.post(
        url(member),
        json={"discord_id": DISCORD_ID, "discord_username": " @new.handle "},
    )
    assert response.status_code == 200, response.text
    assert response.json()["account_status"] == "claimed"
    assert response.json()["account_id"] == account.id
    assert response.json()["account_discord_username"] == "new.handle"
    db_session.refresh(account)
    db_session.refresh(member)
    assert account.discord_id == DISCORD_ID
    assert account.pending_discord_username is None
    assert account.role is UserRole.MEMBER
    assert member.resume_md == "keep this" and member.joined_at == datetime(2020, 1, 1)
    assert db_session.query(User).count() == 3
    assert client.get("/api/auth/me").json()["id"] == admin_id
    assert (
        client.get("/api/activity/options").json()["users"][0]["name"] == "Test member"
    )
    assert db_session.query(MessageEvent).count() == 1


def test_link_uses_verified_pending_metadata_and_removes_queue(
    client_factory, db_session
):
    client, login = client_factory
    member, account = seed_member(db_session)
    db_session.add(
        PendingDiscordLink(
            discord_id=DISCORD_ID,
            discord_username="verified.handle",
            discord_global_name="Verified",
            first_seen_at=datetime(2026, 1, 1),
        )
    )
    db_session.commit()
    login("admin")
    assert (
        client.post(
            url(member), json={"discord_id": DISCORD_ID, "discord_username": "typed"}
        ).status_code
        == 200
    )
    db_session.refresh(account)
    assert account.discord_username == "verified.handle"
    assert account.discord_global_name == "Verified"
    assert db_session.query(PendingDiscordLink).count() == 0


def test_admin_only_and_no_bot_token_access(client_factory, db_session):
    client, login = client_factory
    member, account = seed_member(db_session)
    assert (
        client.post(
            url(member),
            json={"discord_id": DISCORD_ID},
            headers={"Authorization": "Bearer token"},
        ).status_code
        == 401
    )
    login("viewer")
    assert client.post(url(member), json={"discord_id": DISCORD_ID}).status_code == 403
    viewer = db_session.query(User).filter_by(username="viewer").one()
    viewer.role = UserRole.MEMBER
    db_session.commit()
    assert client.post(url(member), json={"discord_id": DISCORD_ID}).status_code == 403
    db_session.refresh(account)
    assert account.discord_id is None


@pytest.mark.parametrize(
    "payload",
    [
        {"discord_id": 123},
        {"discord_id": "@name"},
        {"discord_id": "123.4"},
        {"discord_id": "0"},
        {"discord_id": "1" * 21},
        {"discord_id": ""},
        {"discord_id": None},
        {},
        {"discord_id": DISCORD_ID, "role": "admin"},
    ],
)
def test_rejects_invalid_or_unexpected_payload(client_factory, db_session, payload):
    client, login = client_factory
    member, account = seed_member(db_session)
    login("admin")
    assert client.post(url(member), json=payload).status_code == 422
    db_session.refresh(account)
    assert account.discord_id is None


def test_duplicate_id_and_already_linked_member_cannot_be_reassigned(
    client_factory, db_session
):
    client, login = client_factory
    member, account = seed_member(db_session)
    other, other_account = seed_member(db_session, linked=DISCORD_ID)
    login("admin")
    assert client.post(url(member), json={"discord_id": DISCORD_ID}).status_code == 409
    assert client.post(url(other), json={"discord_id": "222"}).status_code == 409
    db_session.refresh(account)
    db_session.refresh(other_account)
    assert account.discord_id is None and other_account.discord_id == DISCORD_ID


def test_suspended_missing_and_legacy_accounts_are_not_linked(
    client_factory, db_session
):
    client, login = client_factory
    member, account = seed_member(db_session, active=False)
    orphan = Member(real_name="Legacy", graduation_year=2026, institution="Test")
    db_session.add(orphan)
    db_session.commit()
    login("admin")
    assert client.post(url(member), json={"discord_id": DISCORD_ID}).status_code == 409
    assert client.post(url(orphan), json={"discord_id": DISCORD_ID}).status_code == 409
    assert (
        client.post(
            "/api/members/99999/discord-link", json={"discord_id": DISCORD_ID}
        ).status_code
        == 404
    )
    db_session.refresh(account)
    assert not account.is_active and account.discord_id is None


def test_next_oauth_login_reuses_link_and_still_checks_guild(
    client_factory, db_session, monkeypatch
):
    client, login = client_factory
    member, account = seed_member(db_session)
    db_session.add(AppConfig(key="discord_guild_id", value="999"))
    db_session.commit()
    login("admin")
    assert client.post(url(member), json={"discord_id": DISCORD_ID}).status_code == 200
    monkeypatch.setattr(settings, "discord_client_id", "test-id")
    monkeypatch.setattr(settings, "discord_client_secret", "test-secret")
    monkeypatch.setattr(
        settings, "discord_redirect_uri", "http://testserver/api/auth/discord/callback"
    )
    monkeypatch.setattr(discord_oauth, "exchange_code", lambda code: "token")
    monkeypatch.setattr(
        discord_oauth,
        "fetch_identity",
        lambda token: discord_oauth.DiscordIdentity(
            id=DISCORD_ID, username="fresh.handle", global_name="Fresh name"
        ),
    )
    for membership, expected in [
        ("not_member", "/login?error=not_member"),
        ("member", "/"),
    ]:
        client.cookies.clear()
        monkeypatch.setattr(
            discord_oauth,
            "check_guild_membership",
            lambda token, guild, result=membership: result,
        )
        response = client.get("/api/auth/discord/login", follow_redirects=False)
        state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
        callback = client.get(
            "/api/auth/discord/callback",
            params={"code": "test", "state": state},
            follow_redirects=False,
        )
        assert callback.headers["location"] == expected
    assert client.get("/api/auth/me").json()["id"] == account.id
    assert client.get("/api/auth/me").json()["member_id"] == member.id
    db_session.refresh(account)
    assert account.discord_username == "fresh.handle"
    assert db_session.query(User).count() == 3


@pytest.mark.parametrize("same_member", [True, False])
def test_concurrent_admin_links_allow_one_winner(db_session, db_engine, same_member):
    first, _ = seed_member(db_session)
    second, _ = seed_member(db_session)
    first_id, second_id = first.id, second.id
    db_session.commit()
    barrier = Barrier(2)

    def submit(member_id, discord_id):
        with Session(db_engine) as db:
            barrier.wait(timeout=5)
            try:
                response = manually_link_discord(
                    member_id,
                    MemberDiscordLinkRequest(discord_id=discord_id),
                    db,
                    User(id=99, role=UserRole.ADMIN),
                )
                return response.account_status
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(submit, first_id, DISCORD_ID)
        b = pool.submit(
            submit,
            first_id if same_member else second_id,
            "222" if same_member else DISCORD_ID,
        )
        results = [a.result(timeout=10), b.result(timeout=10)]
    assert sorted(results, key=str) == [409, "claimed"]
    db_session.expire_all()
    assert (
        len(db_session.scalars(select(User).where(User.discord_id.is_not(None))).all())
        == 1
    )
