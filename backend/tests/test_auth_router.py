import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole


@pytest.fixture
def client(db_session):
    """TestClient wired to the in-memory db_session via dependency override."""
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


def test_login_admin_password_returns_admin_user(client):
    r = client.post("/api/auth/login", json={"password": "admin-pw"})

    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert "id" in body
    assert "password_hash" not in body
    assert "session" in r.cookies


def test_login_viewer_password_returns_viewer_user(client):
    r = client.post("/api/auth/login", json={"password": "viewer-pw"})

    assert r.status_code == 200
    assert r.json()["role"] == "viewer"


def test_login_wrong_password_returns_401(client):
    r = client.post("/api/auth/login", json={"password": "WRONG"})

    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid password"


def test_suspended_password_account_cannot_login(client, db_session):
    viewer = db_session.query(User).filter_by(username="viewer").one()
    viewer.is_active = False
    db_session.commit()
    r = client.post("/api/auth/login", json={"password": "viewer-pw"})
    assert r.status_code == 403


def test_login_rejects_empty_password(client):
    r = client.post("/api/auth/login", json={"password": ""})
    assert r.status_code == 422


def test_login_rejects_missing_password(client):
    r = client.post("/api/auth/login", json={})
    assert r.status_code == 422


# ---------- audit log ----------


def test_failed_login_writes_audit_line(client, audit_log_dir):
    r = client.post(
        "/api/auth/login",
        json={"password": "WRONG"},
        headers={"x-real-ip": "203.0.113.7"},
    )
    assert r.status_code == 401

    log = (audit_log_dir / "auth.log").read_text(encoding="utf-8")
    assert "login_failed" in log
    assert "ip=203.0.113.7" in log


def test_successful_login_does_not_write_audit_line(client, audit_log_dir):
    r = client.post("/api/auth/login", json={"password": "admin-pw"})
    assert r.status_code == 200

    log_file = audit_log_dir / "auth.log"
    # Either the file was never created (no logger triggered) or it's empty.
    assert not log_file.exists() or log_file.read_text(encoding="utf-8") == ""


def test_brute_forced_success_writes_suspicious_audit_line(client, audit_log_dir):
    headers = {"x-real-ip": "198.51.100.9"}

    from app.core import audit_log as audit

    for _ in range(audit.FAIL_THRESHOLD):
        client.post("/api/auth/login", json={"password": "WRONG"}, headers=headers)

    r = client.post("/api/auth/login", json={"password": "admin-pw"}, headers=headers)
    assert r.status_code == 200

    log = (audit_log_dir / "auth.log").read_text(encoding="utf-8")
    assert "login_success_after_failures" in log
    assert "ip=198.51.100.9" in log
    assert "role=admin" in log


# ---------- per-IP rate limit ----------


def test_login_rate_limit_blocks_sixth_request_from_same_ip(client):
    # The route is decorated with @limiter.limit("5/minute"), so the 6th
    # request within a minute from one IP must come back as 429 — even
    # before bcrypt runs, so this also rules out the bcrypt-cost amplifier.
    headers = {"X-Real-IP": "10.0.0.1"}
    for _ in range(5):
        r = client.post(
            "/api/auth/login",
            json={"password": "WRONG"},
            headers=headers,
        )
        assert r.status_code == 401, r.text

    r = client.post(
        "/api/auth/login",
        json={"password": "WRONG"},
        headers=headers,
    )
    assert r.status_code == 429, r.text


def test_login_rate_limit_keys_on_real_ip_not_spoofed_forwarded_for(client):
    # Regression for the X-Forwarded-For bypass: rotating XFF per request
    # must NOT mint fresh buckets. With a fixed nginx-set X-Real-IP, every
    # attempt shares one bucket regardless of the client-forged XFF, so the
    # 6th still 429s.
    real = {"X-Real-IP": "77.0.0.1"}
    for i in range(5):
        r = client.post(
            "/api/auth/login",
            json={"password": "WRONG"},
            headers={**real, "X-Forwarded-For": f"45.0.0.{i}"},
        )
        assert r.status_code == 401, r.text
    r = client.post(
        "/api/auth/login",
        json={"password": "WRONG"},
        headers={**real, "X-Forwarded-For": "45.0.0.99"},
    )
    assert r.status_code == 429, r.text


def test_login_rate_limit_isolated_per_ip(client):
    # Two different X-Real-IP sources keep separate counters, so one attacker
    # can't lock out other users from the same login route.
    bad = {"X-Real-IP": "10.0.0.2"}
    good = {"X-Real-IP": "10.0.0.3"}

    for _ in range(5):
        r = client.post("/api/auth/login", json={"password": "WRONG"}, headers=bad)
        assert r.status_code == 401

    # IP `bad` is now over the limit.
    r = client.post("/api/auth/login", json={"password": "WRONG"}, headers=bad)
    assert r.status_code == 429

    # IP `good` is unaffected and the real password still gets through.
    r = client.post(
        "/api/auth/login",
        json={"password": "admin-pw"},
        headers=good,
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"


def test_login_rate_limit_counts_successful_attempts_too(client):
    # A real user logging in 5 times in a minute then hitting the limit
    # is documented behavior — counts everything. The 6th call returns
    # 429 even though credentials are correct.
    headers = {"X-Real-IP": "10.0.0.4"}
    for _ in range(5):
        r = client.post(
            "/api/auth/login",
            json={"password": "admin-pw"},
            headers=headers,
        )
        assert r.status_code == 200

    r = client.post(
        "/api/auth/login",
        json={"password": "admin-pw"},
        headers=headers,
    )
    assert r.status_code == 429


def test_me_without_login_returns_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_after_login_returns_current_user(client):
    client.post("/api/auth/login", json={"password": "viewer-pw"})
    r = client.get("/api/auth/me")

    assert r.status_code == 200
    assert r.json()["username"] == "viewer"
    assert r.json()["role"] == "viewer"


def test_me_reports_has_profile_false_for_account_without_member(client):
    client.post("/api/auth/login", json={"password": "admin-pw"})
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["has_profile"] is False


def test_me_reports_is_active(client):
    client.post("/api/auth/login", json={"password": "admin-pw"})
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["is_active"] is True


def test_me_returns_member_real_name_when_linked(client, db_session):
    admin = db_session.query(User).filter_by(username="admin").one()
    db_session.add(
        Member(
            user_id=admin.id,
            graduation_year=2024,
            real_name="王小明",
            institution="NTU",
        )
    )
    db_session.commit()

    client.post("/api/auth/login", json={"password": "admin-pw"})
    r = client.get("/api/auth/me")

    assert r.status_code == 200
    body = r.json()
    assert body["has_profile"] is True
    assert body["member_name"] == "王小明"


def test_logout_clears_session(client):
    client.post("/api/auth/login", json={"password": "admin-pw"})
    assert client.get("/api/auth/me").status_code == 200

    r = client.post("/api/auth/logout")
    assert r.status_code == 204

    assert client.get("/api/auth/me").status_code == 401


def test_full_session_lifecycle(client):
    assert client.get("/api/auth/me").status_code == 401

    login = client.post("/api/auth/login", json={"password": "admin-pw"})
    assert login.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204

    assert client.get("/api/auth/me").status_code == 401


# ---------- admin account management ----------


def _login_admin(client):
    r = client.post("/api/auth/login", json={"password": "admin-pw"})
    assert r.status_code == 200


def _login_viewer(client):
    r = client.post("/api/auth/login", json={"password": "viewer-pw"})
    assert r.status_code == 200


def test_list_users_requires_login(client):
    r = client.get("/api/auth/users")
    assert r.status_code == 401


def test_list_users_forbidden_for_viewer(client):
    _login_viewer(client)
    r = client.get("/api/auth/users")
    assert r.status_code == 403


def test_list_users_returns_both_accounts_for_admin(client):
    _login_admin(client)
    r = client.get("/api/auth/users")

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    roles = {u["role"] for u in body}
    assert roles == {"admin", "viewer"}
    for u in body:
        assert "password_hash" not in u


def test_update_viewer_username_succeeds(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/username",
        json={"username": "watcher"},
    )

    assert r.status_code == 200
    assert r.json()["username"] == "watcher"
    assert r.json()["role"] == "viewer"


def test_update_username_conflicts_when_role_is_ambiguous(client, db_session):
    # Two accounts share a role -> targeting by role is ambiguous. Must 409,
    # not 500 (the old .one_or_none() raised MultipleResultsFound).
    db_session.add(
        User(
            username="viewer2",
            password_hash=hash_password("viewer2-pw"),
            role=UserRole.VIEWER,
        )
    )
    db_session.commit()
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/username",
        json={"username": "watcher"},
    )
    assert r.status_code == 409, r.text


def test_update_admin_username_succeeds_and_me_reflects_it(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/admin/username",
        json={"username": "boss"},
    )
    assert r.status_code == 200

    me = client.get("/api/auth/me")
    assert me.json()["username"] == "boss"


def test_update_username_rejects_collision(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/username",
        json={"username": "admin"},
    )
    assert r.status_code == 409


def test_update_username_allows_same_value(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/admin/username",
        json={"username": "admin"},
    )
    assert r.status_code == 200


def test_update_username_rejects_empty(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/username",
        json={"username": ""},
    )
    assert r.status_code == 422


def test_update_username_forbidden_for_viewer(client):
    _login_viewer(client)
    r = client.patch(
        "/api/auth/users/viewer/username",
        json={"username": "watcher"},
    )
    assert r.status_code == 403


def test_update_username_unauthenticated(client):
    r = client.patch(
        "/api/auth/users/viewer/username",
        json={"username": "watcher"},
    )
    assert r.status_code == 401


def test_update_password_succeeds_and_new_password_logs_in(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "admin-pw", "new_password": "fresh-pw"},
    )
    assert r.status_code == 204

    client.post("/api/auth/logout")

    bad = client.post("/api/auth/login", json={"password": "viewer-pw"})
    assert bad.status_code == 401

    ok = client.post("/api/auth/login", json={"password": "fresh-pw"})
    assert ok.status_code == 200
    assert ok.json()["role"] == "viewer"


def test_update_admin_password_then_relogin(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/admin/password",
        json={"current_password": "admin-pw", "new_password": "rotated-pw"},
    )
    assert r.status_code == 204

    client.post("/api/auth/logout")

    ok = client.post("/api/auth/login", json={"password": "rotated-pw"})
    assert ok.status_code == 200
    assert ok.json()["role"] == "admin"


def test_password_change_confirms_against_the_admin_account_not_the_actor(
    client, db_session
):
    # A second admin whose own password differs must confirm password changes
    # with THE admin account's password — so a Discord-linked admin (no
    # password of their own) can manage accounts using the shared admin one.
    db_session.add(
        User(
            username="admin2",
            password_hash=hash_password("admin2-pw"),
            role=UserRole.ADMIN,
        )
    )
    db_session.commit()
    assert (
        client.post("/api/auth/login", json={"password": "admin2-pw"}).status_code
        == 200
    )
    # The actor's OWN password is not accepted as confirmation.
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "admin2-pw", "new_password": "vfresh-pw"},
    )
    assert r.status_code == 422, r.text
    # THE admin account's password is.
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "admin-pw", "new_password": "vfresh-pw"},
    )
    assert r.status_code == 204, r.text


def test_update_password_wrong_current_returns_422(client):
    # 422 (not 401) so the frontend's global session-expired interceptor
    # doesn't bounce a typo'd current password back to /login while the
    # admin session is still valid.
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "WRONG", "new_password": "fresh-pw"},
    )
    assert r.status_code == 422


def test_update_password_collision_with_other_account(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "admin-pw", "new_password": "admin-pw"},
    )
    assert r.status_code == 409


def test_update_password_forbidden_for_viewer(client):
    _login_viewer(client)
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "viewer-pw", "new_password": "x"},
    )
    assert r.status_code == 403


def test_update_password_unauthenticated(client):
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "admin-pw", "new_password": "x"},
    )
    assert r.status_code == 401


def test_update_password_rejects_empty_new_password(client):
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "admin-pw", "new_password": ""},
    )
    assert r.status_code == 422


# ---------- session invalidation on password change ----------


def test_changing_viewer_password_evicts_other_viewer_session(client):
    # Viewer logs in on "device A" (this client). Admin logs in on a
    # second client and rotates the viewer's password. The viewer's
    # session must be rejected on the next request.
    client.post("/api/auth/login", json={"password": "viewer-pw"})
    assert client.get("/api/auth/me").status_code == 200

    with TestClient(app) as admin_client:
        admin_client.post("/api/auth/login", json={"password": "admin-pw"})
        r = admin_client.patch(
            "/api/auth/users/viewer/password",
            json={"current_password": "admin-pw", "new_password": "fresh-pw"},
        )
        assert r.status_code == 204

    assert client.get("/api/auth/me").status_code == 401


def test_changing_admin_password_evicts_other_admin_session(client):
    # Admin "device A" logs in here; admin "device B" rotates the
    # password. Device A's session must be rejected.
    client.post("/api/auth/login", json={"password": "admin-pw"})
    assert client.get("/api/auth/me").status_code == 200

    with TestClient(app) as admin_b:
        admin_b.post("/api/auth/login", json={"password": "admin-pw"})
        r = admin_b.patch(
            "/api/auth/users/admin/password",
            json={"current_password": "admin-pw", "new_password": "rotated-pw"},
        )
        assert r.status_code == 204

    assert client.get("/api/auth/me").status_code == 401


def test_admin_changing_own_password_keeps_current_session_alive(client):
    # The session that performs the rotation should be re-stamped with
    # the new version so the admin doesn't have to re-login from the
    # very browser they just used.
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/admin/password",
        json={"current_password": "admin-pw", "new_password": "rotated-pw"},
    )
    assert r.status_code == 204

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_admin_changing_viewer_password_keeps_admin_session_alive(client):
    # Rotating someone else's password must not affect the actor's session.
    _login_admin(client)
    r = client.patch(
        "/api/auth/users/viewer/password",
        json={"current_password": "admin-pw", "new_password": "fresh-pw"},
    )
    assert r.status_code == 204

    assert client.get("/api/auth/me").status_code == 200


def test_stale_password_version_in_db_evicts_session(client, db_session):
    # Simulates either an admin rotating the password through some
    # out-of-band channel, or a freshly-deployed bump where the cookie
    # was issued before the column existed.
    client.post("/api/auth/login", json={"password": "viewer-pw"})
    assert client.get("/api/auth/me").status_code == 200

    viewer = db_session.query(User).filter_by(role=UserRole.VIEWER).one()
    viewer.password_version += 1
    db_session.commit()

    assert client.get("/api/auth/me").status_code == 401


def _login_admin(client):
    assert (
        client.post("/api/auth/login", json={"password": "admin-pw"}).status_code == 200
    )


def test_suspend_member_succeeds(client, db_session):
    m = User(
        role=UserRole.MEMBER, discord_id="m1", discord_username="m", is_active=True
    )
    db_session.add(m)
    db_session.commit()
    _login_admin(client)
    r = client.patch(f"/api/auth/users/{m.id}/active", json={"is_active": False})
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False


def test_reactivate_member_succeeds(client, db_session):
    m = User(
        role=UserRole.MEMBER, discord_id="m2", discord_username="m", is_active=False
    )
    db_session.add(m)
    db_session.commit()
    _login_admin(client)
    r = client.patch(f"/api/auth/users/{m.id}/active", json={"is_active": True})
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is True


def test_suspend_viewer_succeeds(client, db_session):
    viewer = db_session.query(User).filter_by(username="viewer").one()
    _login_admin(client)
    r = client.patch(f"/api/auth/users/{viewer.id}/active", json={"is_active": False})
    assert r.status_code == 200, r.text


def test_cannot_suspend_admin_role(client, db_session, monkeypatch):
    # Make sure G2 doesn't fire for this one: protect a different username.
    monkeypatch.setattr(settings, "seed_admin_username", "__none__")
    other_admin = User(
        role=UserRole.ADMIN, discord_id="a2", discord_username="a2", is_active=True
    )
    db_session.add(other_admin)
    db_session.commit()
    _login_admin(client)
    r = client.patch(
        f"/api/auth/users/{other_admin.id}/active", json={"is_active": False}
    )
    assert r.status_code == 409, r.text


def test_cannot_suspend_seed_admin(client, db_session, monkeypatch):
    # G2: the seeded 'admin' account is the break-glass account; protect it.
    monkeypatch.setattr(settings, "seed_admin_username", "admin")
    seed = db_session.query(User).filter_by(username="admin").one()
    _login_admin(client)
    r = client.patch(f"/api/auth/users/{seed.id}/active", json={"is_active": False})
    assert r.status_code == 409, r.text
    assert (
        "break-glass" in r.json()["detail"].lower()
        or "admin" in r.json()["detail"].lower()
    )


def test_non_admin_cannot_suspend(client, db_session):
    m = User(
        role=UserRole.MEMBER, discord_id="m3", discord_username="m", is_active=True
    )
    db_session.add(m)
    db_session.commit()
    client.post("/api/auth/login", json={"password": "viewer-pw"})  # viewer, not admin
    r = client.patch(f"/api/auth/users/{m.id}/active", json={"is_active": False})
    assert r.status_code == 403, r.text


def test_cannot_promote_suspended_account_to_admin(client, db_session):
    suspended = User(
        role=UserRole.MEMBER, discord_id="susp1", discord_username="s", is_active=False
    )
    db_session.add(suspended)
    db_session.commit()
    _login_admin(client)
    r = client.patch(f"/api/auth/users/{suspended.id}/role", json={"role": "admin"})
    assert r.status_code == 409, r.text


def test_can_still_promote_active_member_to_admin(client, db_session):
    active = User(
        role=UserRole.MEMBER, discord_id="act1", discord_username="a", is_active=True
    )
    db_session.add(active)
    db_session.commit()
    _login_admin(client)
    r = client.patch(f"/api/auth/users/{active.id}/role", json={"role": "admin"})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"


def test_resolve_pending_link_rejects_already_bound_discord_id(client, db_session):
    from datetime import UTC, datetime

    from app.models import PendingDiscordLink

    # An account already bound to discord_id "7".
    bound = User(role=UserRole.MEMBER, discord_id="7", discord_username="ghost")
    db_session.add(bound)
    # A stale pending row for the same identity.
    db_session.add(
        PendingDiscordLink(
            discord_id="7", discord_username="ghost", first_seen_at=datetime.now(UTC)
        )
    )
    # A different unclaimed member to try to resolve onto.
    other = User(role=UserRole.MEMBER)
    db_session.add(other)
    db_session.flush()
    member = Member(
        graduation_year=2024, real_name="王小明", institution="X", user_id=other.id
    )
    db_session.add(member)
    db_session.commit()

    _login_admin(client)
    r = client.post("/api/auth/pending-links/7/resolve", json={"member_id": member.id})
    assert r.status_code == 409, r.text
