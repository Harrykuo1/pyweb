import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Event, Member, PostStatus, User, UserRole


@pytest.fixture
def ctx(db_session):
    admin = User(
        username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN
    )
    viewer = User(
        username="viewer",
        password_hash=hash_password("viewer-pw"),
        role=UserRole.VIEWER,
    )
    mem = User(
        username="mem", password_hash=hash_password("mem-pw"), role=UserRole.MEMBER
    )
    np = User(username="np", password_hash=hash_password("np-pw"), role=UserRole.MEMBER)
    otheru = User(
        username="otheru", password_hash=hash_password("other-pw"), role=UserRole.MEMBER
    )
    db_session.add_all([admin, viewer, mem, np, otheru])
    db_session.flush()
    db_session.add_all(
        [
            Member(
                graduation_year=2024,
                real_name="我本人",
                institution="X",
                user_id=mem.id,
            ),
            Member(
                graduation_year=2024,
                real_name="別人",
                institution="Y",
                user_id=otheru.id,
            ),
        ]
    )
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    def login(pw):
        assert client.post("/api/auth/login", json={"password": pw}).status_code == 200

    try:
        yield client, login
    finally:
        client.close()
        app.dependency_overrides.clear()


def _ev(**kw):
    p = {"title": "聚餐", "event_date": "2026-03-01"}
    p.update(kw)
    return p


def _member_creates(client, login, **kw):
    login("mem-pw")
    r = client.post("/api/events", json=_ev(**kw))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_admin_create_is_accepted(ctx):
    client, login = ctx
    login("admin-pw")
    r = client.post("/api/events", json=_ev())
    assert r.status_code == 201
    assert r.json()["status"] == "accepted"


def test_member_create_is_pending_with_author(ctx):
    client, login = ctx
    login("mem-pw")
    r = client.post("/api/events", json=_ev())
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["author_display_name"] == "我本人"
    assert body["can_edit"] is True


def test_viewer_cannot_create_event(ctx):
    client, login = ctx
    login("viewer-pw")
    assert client.post("/api/events", json=_ev()).status_code == 403


def test_member_without_profile_cannot_create_event(ctx):
    # A member who registered but hasn't completed their profile (no
    # Member row) must not be able to post content — otherwise they can
    # publish without ever showing up in the members-first admin roster.
    client, login = ctx
    login("np-pw")
    assert client.post("/api/events", json=_ev()).status_code == 403


def test_owner_can_update_own_event(ctx):
    client, login = ctx
    eid = _member_creates(client, login)
    r = client.put(f"/api/events/{eid}", json={"title": "改名"})
    assert r.status_code == 200
    assert r.json()["title"] == "改名"


def test_non_owner_member_cannot_update_event(ctx):
    client, login = ctx
    eid = _member_creates(client, login)
    client.post("/api/auth/logout")
    login("other-pw")
    assert client.put(f"/api/events/{eid}", json={"title": "hijack"}).status_code == 403


def test_member_editing_rejected_event_resubmits(ctx, db_session):
    client, login = ctx
    eid = _member_creates(client, login)
    db_session.query(Event).filter_by(id=eid).update({"status": PostStatus.REJECTED})
    db_session.commit()
    r = client.put(f"/api/events/{eid}", json={"description_md": "revised"})
    assert r.json()["status"] == "pending"


def test_event_resubmit_clears_stale_review_state(ctx, db_session):
    client, login = ctx
    eid = _member_creates(client, login)
    db_session.query(Event).filter_by(id=eid).update(
        {"status": PostStatus.REJECTED, "review_reason": "缺少細節"}
    )
    db_session.commit()
    r = client.put(f"/api/events/{eid}", json={"description_md": "revised"})
    assert r.json()["status"] == "pending"
    db_session.expire_all()
    row = db_session.query(Event).filter_by(id=eid).first()
    assert row.review_reason is None


def test_member_editing_accepted_event_returns_to_pending(ctx, db_session):
    client, login = ctx
    eid = _member_creates(client, login)
    db_session.query(Event).filter_by(id=eid).update({"status": PostStatus.ACCEPTED})
    db_session.commit()
    r = client.put(f"/api/events/{eid}", json={"description_md": "sneaky edit"})
    # Editing public content re-enters the review queue; it must not stay live.
    assert r.json()["status"] == "pending"


def test_admin_editing_accepted_event_stays_accepted(ctx, db_session):
    client, login = ctx
    eid = _member_creates(client, login)
    db_session.query(Event).filter_by(id=eid).update({"status": PostStatus.ACCEPTED})
    db_session.commit()
    client.post("/api/auth/logout")
    login("admin-pw")
    r = client.put(f"/api/events/{eid}", json={"description_md": "admin edit"})
    # Admin edits are trusted and do not bounce the event back to review.
    assert r.json()["status"] == "accepted"


def test_owner_deletes_own_event_without_password(ctx):
    client, login = ctx
    eid = _member_creates(client, login)
    assert client.request("DELETE", f"/api/events/{eid}").status_code == 204


def test_admin_accept_and_reject_event(ctx):
    client, login = ctx
    eid = _member_creates(client, login)
    client.post("/api/auth/logout")
    login("admin-pw")
    assert client.post(f"/api/events/{eid}/accept").json()["status"] == "accepted"
    r = client.post(f"/api/events/{eid}/reject", json={"reason": "重複"})
    assert r.json()["status"] == "rejected"
    assert r.json()["review_reason"] == "重複"


def test_member_cannot_accept_event(ctx):
    client, login = ctx
    eid = _member_creates(client, login)
    assert client.post(f"/api/events/{eid}/accept").status_code == 403
