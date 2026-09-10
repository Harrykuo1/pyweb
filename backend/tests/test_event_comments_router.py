from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Event, EventComment, Member, PostStatus, User, UserRole


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
    other = User(
        username="other", password_hash=hash_password("other-pw"), role=UserRole.MEMBER
    )
    np = User(username="np", password_hash=hash_password("np-pw"), role=UserRole.MEMBER)
    db_session.add_all([admin, viewer, mem, other, np])
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
                user_id=other.id,
            ),
        ]
    )
    # An accepted event authored by mem — visible to everyone, so any member
    # can comment on it.
    event = Event(
        title="聚餐",
        event_date=date(2026, 3, 1),
        author_user_id=mem.id,
        status=PostStatus.ACCEPTED,
    )
    db_session.add(event)
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    def login(pw):
        assert client.post("/api/auth/login", json={"password": pw}).status_code == 200

    try:
        yield client, login, event.id
    finally:
        client.close()
        app.dependency_overrides.clear()


def _comment(client, event_id, body="讚"):
    return client.post(f"/api/events/{event_id}/comments", json={"body": body})


def test_member_can_comment(ctx):
    client, login, eid = ctx
    login("mem-pw")
    r = _comment(client, eid, "很好玩")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["body"] == "很好玩"
    assert body["author_display_name"] == "我本人"
    assert body["edited_at"] is None
    assert body["can_edit"] is True
    assert body["can_delete"] is True


def test_comment_exposes_author_member_and_photo(ctx, db_session):
    client, login, eid = ctx
    # Give mem's member profile a photo so has_photo/updated_at are populated.
    from datetime import UTC, datetime

    from app.models import Member, User

    mem = db_session.query(User).filter_by(username="mem").one()
    member = db_session.query(Member).filter_by(user_id=mem.id).one()
    member.photo_content_type = "image/png"
    member.photo_updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    db_session.commit()

    login("mem-pw")
    body = _comment(client, eid, "帶頭貼").json()
    assert body["author_member_id"] == member.id
    assert body["author_has_photo"] is True
    assert body["author_photo_updated_at"] is not None


def test_admin_author_has_no_member_or_photo(ctx):
    # An admin has no member profile, so avatar falls back to the initial.
    client, login, eid = ctx
    login("admin-pw")
    body = _comment(client, eid, "admin 留言").json()
    assert body["author_member_id"] is None
    assert body["author_has_photo"] is False


def test_comment_body_is_trimmed_and_blank_rejected(ctx):
    client, login, eid = ctx
    login("mem-pw")
    assert _comment(client, eid, "  邊界  ").json()["body"] == "邊界"
    assert _comment(client, eid, "   ").status_code == 422
    assert _comment(client, eid, "").status_code == 422


def test_viewer_cannot_comment(ctx):
    client, login, eid = ctx
    login("viewer-pw")
    assert _comment(client, eid).status_code == 403


def test_member_without_profile_cannot_comment(ctx):
    client, login, eid = ctx
    login("np-pw")
    assert _comment(client, eid).status_code == 403


def test_comment_on_missing_event_is_404(ctx):
    client, login, _ = ctx
    login("mem-pw")
    assert _comment(client, 999999).status_code == 404


def test_list_returns_comments_oldest_first_with_flags(ctx):
    client, login, eid = ctx
    login("mem-pw")
    _comment(client, eid, "一")
    _comment(client, eid, "二")
    client.post("/api/auth/logout")
    login("other-pw")
    _comment(client, eid, "三")

    r = client.get(f"/api/events/{eid}/comments")
    assert r.status_code == 200
    items = r.json()
    assert [c["body"] for c in items] == ["一", "二", "三"]
    # other can edit/delete only their own (the third) comment.
    assert [c["can_edit"] for c in items] == [False, False, True]
    assert [c["can_delete"] for c in items] == [False, False, True]


def test_author_can_edit_own_comment_and_stamps_edited_at(ctx):
    client, login, eid = ctx
    login("mem-pw")
    cid = _comment(client, eid, "打錯字").json()["id"]
    r = client.put(f"/api/events/{eid}/comments/{cid}", json={"body": "更正"})
    assert r.status_code == 200
    body = r.json()
    assert body["body"] == "更正"
    assert body["edited_at"] is not None


def test_non_author_member_cannot_edit_comment(ctx):
    client, login, eid = ctx
    login("mem-pw")
    cid = _comment(client, eid).json()["id"]
    client.post("/api/auth/logout")
    login("other-pw")
    r = client.put(f"/api/events/{eid}/comments/{cid}", json={"body": "亂改"})
    assert r.status_code == 403


def test_admin_cannot_edit_another_users_comment(ctx):
    client, login, eid = ctx
    login("mem-pw")
    cid = _comment(client, eid).json()["id"]
    client.post("/api/auth/logout")
    login("admin-pw")
    r = client.put(f"/api/events/{eid}/comments/{cid}", json={"body": "admin 改"})
    assert r.status_code == 403


def test_author_deletes_own_comment_without_password(ctx):
    client, login, eid = ctx
    login("mem-pw")
    cid = _comment(client, eid).json()["id"]
    assert (
        client.request("DELETE", f"/api/events/{eid}/comments/{cid}").status_code == 204
    )


def test_non_author_member_cannot_delete_comment(ctx):
    client, login, eid = ctx
    login("mem-pw")
    cid = _comment(client, eid).json()["id"]
    client.post("/api/auth/logout")
    login("other-pw")
    assert (
        client.request("DELETE", f"/api/events/{eid}/comments/{cid}").status_code == 403
    )


def test_admin_deletes_others_comment_requires_password(ctx, db_session):
    client, login, eid = ctx
    login("mem-pw")
    cid = _comment(client, eid).json()["id"]
    client.post("/api/auth/logout")
    login("admin-pw")

    # No body → 422; wrong password → 422; correct password → 204.
    assert (
        client.request("DELETE", f"/api/events/{eid}/comments/{cid}").status_code == 422
    )
    assert (
        client.request(
            "DELETE", f"/api/events/{eid}/comments/{cid}", json={"password": "nope"}
        ).status_code
        == 422
    )
    ok = client.request(
        "DELETE", f"/api/events/{eid}/comments/{cid}", json={"password": "admin-pw"}
    )
    assert ok.status_code == 204
    assert db_session.query(EventComment).filter_by(id=cid).count() == 0


def test_admin_deletes_own_comment_without_password(ctx):
    client, login, eid = ctx
    login("admin-pw")
    cid = _comment(client, eid).json()["id"]
    # The admin authored this one, so no confirmation password is required.
    assert (
        client.request("DELETE", f"/api/events/{eid}/comments/{cid}").status_code == 204
    )


def test_pending_event_is_invisible_to_other_members_on_comment_endpoints(
    ctx, db_session
):
    # Same rule as the like endpoints, enforced by a separate copy here.
    client, login, _ = ctx
    author_id = db_session.query(User).filter_by(username="mem").one().id
    pending = Event(
        title="未審核",
        event_date=date(2026, 4, 1),
        author_user_id=author_id,
        status=PostStatus.PENDING,
    )
    db_session.add(pending)
    db_session.commit()

    login("other-pw")
    assert client.get(f"/api/events/{pending.id}/comments").status_code == 404
    assert (
        client.post(
            f"/api/events/{pending.id}/comments", json={"body": "偷看"}
        ).status_code
        == 404
    )

    login("mem-pw")
    assert client.get(f"/api/events/{pending.id}/comments").status_code == 200
    login("admin-pw")
    assert client.get(f"/api/events/{pending.id}/comments").status_code == 200
