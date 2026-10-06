import base64
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import app
from app.models import AppConfig, User, UserRole
from app.routers.members import replace_member_discord_link
from app.schemas.member_discord import MemberDiscordReplaceRequest
from tests import test_discord_auth_router as oauth
from tests import test_manual_discord_link as manual

client_factory = manual.client_factory
configured = oauth.configured
OLD = "123456789012345678"
NEW = "223456789012345678"


def payload(**extra):
    return {"discord_id": NEW, "expected_discord_id": OLD, "confirmed": True, **extra}


def cookie(account):
    data = base64.b64encode(
        json.dumps(
            {"user_id": account.id, "password_version": account.password_version}
        ).encode()
    )
    return TimestampSigner(str(settings.session_secret)).sign(data).decode()


def test_relink_preserves_profile_and_role_but_revokes_old_session(
    client_factory, db_session
):
    client, login = client_factory
    member, account = manual.seed_member(db_session, linked=OLD)
    account.discord_username = "old.handle"
    account.discord_global_name = "Old name"
    account.role = UserRole.ADMIN
    db_session.commit()
    with TestClient(app) as old_client:
        old_client.cookies.set("session", cookie(account))
        assert old_client.get("/api/auth/me").status_code == 200
        login("admin")
        assert client.get(manual.url(member)).json() == {
            "discord_id": OLD,
            "discord_username": "old.handle",
        }
        original_version = account.password_version
        response = client.patch(manual.url(member), json=payload())
        assert response.status_code == 200, response.text
        assert response.json()["account_id"] == account.id
        assert response.json()["resume_md"] == "keep this"
        db_session.refresh(account)
        assert account.discord_id == NEW and account.role is UserRole.ADMIN
        assert account.password_version == original_version + 1
        assert account.discord_username is None and account.discord_global_name is None
        assert account.pending_discord_username is None
        assert old_client.get("/api/auth/me").status_code == 401
        assert client.get("/api/auth/me").status_code == 200


@pytest.mark.parametrize("confirmation", [False, None, 1, "true", "false"])
def test_explicit_boolean_confirmation_is_required(
    client_factory, db_session, confirmation
):
    client, login = client_factory
    member, account = manual.seed_member(db_session, linked=OLD)
    login("admin")
    assert (
        client.patch(
            manual.url(member), json=payload(confirmed=confirmation)
        ).status_code
        == 422
    )
    db_session.refresh(account)
    assert account.discord_id == OLD and account.password_version == 1


def test_missing_confirmation_and_snapshot_rejected(client_factory, db_session):
    client, login = client_factory
    member, _ = manual.seed_member(db_session, linked=OLD)
    login("admin")
    for key in ["confirmed", "expected_discord_id"]:
        body = payload()
        body.pop(key)
        assert client.patch(manual.url(member), json=body).status_code == 422


def test_stale_same_taken_and_suspended_are_rejected(client_factory, db_session):
    client, login = client_factory
    member, account = manual.seed_member(db_session, linked=OLD)
    login("admin")
    for body in [payload(expected_discord_id="999"), payload(discord_id=OLD)]:
        assert client.patch(manual.url(member), json=body).status_code == 409
    manual.seed_member(db_session, linked=NEW)
    assert client.patch(manual.url(member), json=payload()).status_code == 409
    account.is_active = False
    db_session.commit()
    assert (
        client.patch(manual.url(member), json=payload(discord_id="333")).status_code
        == 409
    )
    db_session.refresh(account)
    assert account.discord_id == OLD and account.password_version == 1


def test_read_and_replace_require_admin(client_factory, db_session):
    client, login = client_factory
    member, _ = manual.seed_member(db_session, linked=OLD)
    for expected in [401, 403]:
        assert client.get(manual.url(member)).status_code == expected
        assert client.patch(manual.url(member), json=payload()).status_code == expected
        if expected == 401:
            login("viewer")


def test_pending_account_cannot_use_replacement(client_factory, db_session):
    client, login = client_factory
    member, _ = manual.seed_member(db_session)
    login("admin")
    assert client.patch(manual.url(member), json=payload()).status_code == 409
    assert client.get(manual.url(member)).json()["discord_id"] is None


def test_old_oauth_identity_rejected_and_new_identity_uses_same_account(
    client_factory, db_session, monkeypatch, configured
):
    client, login = client_factory
    member, account = manual.seed_member(db_session, linked=OLD)
    db_session.add(AppConfig(key="discord_guild_id", value="999"))
    db_session.commit()
    login("admin")
    assert client.patch(manual.url(member), json=payload()).status_code == 200
    for discord_id, target in [(OLD, "/login?error=not_linked"), (NEW, "/")]:
        client.cookies.clear()
        oauth._patch_flow(monkeypatch, identity_id=discord_id)
        state = oauth._start_and_get_state(client)
        response = client.get(
            "/api/auth/discord/callback",
            params={"code": "test", "state": state},
            follow_redirects=False,
        )
        assert response.headers["location"] == target
    assert client.get("/api/auth/me").json()["id"] == account.id


def test_relink_racing_oauth_commit_cannot_issue_a_new_valid_old_identity_session(
    client_factory, db_session, db_engine, monkeypatch, configured
):
    client, _ = client_factory
    _, account = manual.seed_member(db_session, linked=OLD)
    account_id = account.id
    db_session.add(AppConfig(key="discord_guild_id", value="999"))
    db_session.commit()
    oauth._patch_flow(monkeypatch, identity_id=OLD)
    state = oauth._start_and_get_state(client)
    original = db_session.commit

    def commit_then_relink():
        original()
        with Session(db_engine) as concurrent:
            target = concurrent.get(User, account_id)
            target.discord_id = NEW
            target.password_version += 1
            concurrent.commit()

    monkeypatch.setattr(db_session, "commit", commit_then_relink)
    response = client.get(
        "/api/auth/discord/callback",
        params={"code": "test", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert client.get("/api/auth/me").status_code == 401


def test_two_replacements_of_one_snapshot_allow_only_one_winner(db_session, db_engine):
    member, _ = manual.seed_member(db_session, linked=OLD)
    member_id = member.id
    db_session.commit()
    barrier = Barrier(2)

    def replace(new_id):
        with Session(db_engine) as db:
            barrier.wait(timeout=5)
            try:
                replace_member_discord_link(
                    member_id,
                    MemberDiscordReplaceRequest(**payload(discord_id=new_id)),
                    db,
                    User(id=99, role=UserRole.ADMIN),
                )
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(replace, NEW)
        b = pool.submit(replace, "333")
        assert sorted([a.result(timeout=10), b.result(timeout=10)]) == [200, 409]


def test_oauth_rechecks_identity_after_concurrent_relink_before_lock(
    client_factory, db_session, db_engine, monkeypatch, configured
):
    from sqlalchemy.orm import Query

    client, _ = client_factory
    _, account = manual.seed_member(db_session, linked=OLD)
    account_id = account.id
    db_session.add(AppConfig(key="discord_guild_id", value="999"))
    db_session.commit()
    oauth._patch_flow(monkeypatch, identity_id=OLD)
    state = oauth._start_and_get_state(client)
    original = Query.populate_existing
    invoked = []

    def replace_before_refresh(query):
        if not invoked and query.column_descriptions[0]["entity"] is User:
            invoked.append(True)
            with Session(db_engine) as concurrent:
                target = concurrent.get(User, account_id)
                target.discord_id = NEW
                target.password_version += 1
                concurrent.commit()
        return original(query)

    monkeypatch.setattr(Query, "populate_existing", replace_before_refresh)
    response = client.get(
        "/api/auth/discord/callback",
        params={"code": "test", "state": state},
        follow_redirects=False,
    )
    assert invoked
    assert response.headers["location"] == "/login?error=not_linked"
    assert client.get("/api/auth/me").status_code == 401
