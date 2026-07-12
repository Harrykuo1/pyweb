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
        client.post("/api/auth/login", json={"password": "admin-pw"}).status_code == 200
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


# ---------- list users ----------


def test_list_users_requires_admin(client):
    assert client.get("/api/auth/users").status_code == 401


def test_list_users_includes_linked_member_name(client, db_session):
    _seed_member_account(db_session, real_name="王小明")
    _login_admin(client)

    r = client.get("/api/auth/users")
    assert r.status_code == 200
    by_role = {u["role"]: u for u in r.json()}
    # The seeded admin has no member profile -> member_name is null.
    assert by_role["admin"]["member_name"] is None
    # The member account surfaces its profile's real name for the admin list.
    assert by_role["member"]["member_name"] == "王小明"


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


# ---------- resolve pending link ----------


def test_resolve_pending_link_attaches_identity_to_member(client, db_session):
    u, m = _seed_member_account(db_session)
    _seed_pending(db_session, "P1")
    _login_admin(client)

    r = client.post(
        "/api/auth/pending-links/P1/resolve",
        json={"member_id": m.id},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "member"

    db_session.expire_all()
    linked = db_session.query(User).filter_by(id=u.id).one()
    assert linked.discord_id == "P1"
    assert linked.discord_username == "ghost"
    assert linked.pending_discord_username is None
    assert db_session.query(PendingDiscordLink).filter_by(discord_id="P1").count() == 0


def test_resolve_pending_link_404_when_pending_missing(client, db_session):
    _, m = _seed_member_account(db_session)
    _login_admin(client)
    r = client.post("/api/auth/pending-links/NOPE/resolve", json={"member_id": m.id})
    assert r.status_code == 404


def test_resolve_pending_link_404_when_member_missing(client, db_session):
    _seed_pending(db_session, "P1")
    _login_admin(client)
    r = client.post("/api/auth/pending-links/P1/resolve", json={"member_id": 9999})
    assert r.status_code == 404


def test_resolve_pending_link_409_when_member_already_linked(client, db_session):
    u, m = _seed_member_account(db_session)
    u.discord_id = "ALREADY"
    db_session.commit()
    _seed_pending(db_session, "P1")
    _login_admin(client)

    r = client.post("/api/auth/pending-links/P1/resolve", json={"member_id": m.id})
    assert r.status_code == 409


def test_resolve_pending_link_requires_admin(client, db_session):
    _, m = _seed_member_account(db_session)
    _seed_pending(db_session, "P1")
    r = client.post("/api/auth/pending-links/P1/resolve", json={"member_id": m.id})
    assert r.status_code == 401


# ---------- delete (dismiss) pending link ----------


def test_delete_pending_link_requires_admin(client, db_session):
    _seed_pending(db_session, "P1")
    assert client.delete("/api/auth/pending-links/P1").status_code == 401


def test_delete_pending_link_removes_row(client, db_session):
    _seed_pending(db_session, "P1")
    _login_admin(client)

    assert client.delete("/api/auth/pending-links/P1").status_code == 204
    assert db_session.query(PendingDiscordLink).filter_by(discord_id="P1").count() == 0


def test_delete_pending_link_404_when_missing(client):
    _login_admin(client)
    assert client.delete("/api/auth/pending-links/nope").status_code == 404


# ---------- assign user role ----------


def test_assign_role_promotes_member_to_admin(client, db_session):
    u, _ = _seed_member_account(db_session)
    _login_admin(client)

    r = client.patch(f"/api/auth/users/{u.id}/role", json={"role": "admin"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"

    db_session.expire_all()
    assert db_session.query(User).filter_by(id=u.id).one().role is UserRole.ADMIN


def test_assign_role_demotes_admin_when_another_admin_exists(client, db_session):
    # The fixture's "admin" plus this one = two admins, so demotion is allowed.
    victim = User(role=UserRole.ADMIN, username="admin2", password_hash="h")
    db_session.add(victim)
    db_session.commit()
    _login_admin(client)

    r = client.patch(f"/api/auth/users/{victim.id}/role", json={"role": "member"})
    assert r.status_code == 200
    assert r.json()["role"] == "member"


def test_assign_role_blocks_demoting_the_last_admin(client, db_session):
    # Only the fixture admin exists; demoting them would lock everyone out.
    admin = db_session.query(User).filter_by(role=UserRole.ADMIN).one()
    _login_admin(client)

    r = client.patch(f"/api/auth/users/{admin.id}/role", json={"role": "member"})
    assert r.status_code == 409


def test_cannot_demote_the_last_password_admin(client, db_session):
    # A Discord-only admin also exists, so the "last admin" guard passes — but
    # demoting the password admin would leave only OAuth admins with no
    # password-login recovery, so it must still be blocked.
    db_session.add(
        User(role=UserRole.ADMIN, discord_id="da", discord_username="d", is_active=True)
    )
    db_session.commit()
    admin = db_session.query(User).filter_by(username="admin").one()
    _login_admin(client)

    r = client.patch(f"/api/auth/users/{admin.id}/role", json={"role": "member"})
    assert r.status_code == 409, r.text
    assert "password" in r.json()["detail"].lower()


def test_can_demote_a_discord_admin_while_a_password_admin_remains(client, db_session):
    # Demoting a Discord-only admin is fine as long as the password recovery
    # admin stays admin.
    d = User(role=UserRole.ADMIN, discord_id="da", discord_username="d", is_active=True)
    db_session.add(d)
    db_session.commit()
    _login_admin(client)

    r = client.patch(f"/api/auth/users/{d.id}/role", json={"role": "member"})
    assert r.status_code == 200, r.text


def test_assign_role_rejects_viewer_target_role(client, db_session):
    u, _ = _seed_member_account(db_session)
    _login_admin(client)
    r = client.patch(f"/api/auth/users/{u.id}/role", json={"role": "viewer"})
    assert r.status_code == 422


def test_assign_role_404_for_unknown_user(client):
    _login_admin(client)
    r = client.patch("/api/auth/users/99999/role", json={"role": "admin"})
    assert r.status_code == 404


def test_assign_role_requires_admin(client, db_session):
    u, _ = _seed_member_account(db_session)
    r = client.patch(f"/api/auth/users/{u.id}/role", json={"role": "admin"})
    assert r.status_code == 401
