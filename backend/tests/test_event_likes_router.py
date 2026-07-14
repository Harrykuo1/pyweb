from datetime import UTC, date, datetime

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
                photo_content_type="image/png",
                photo_updated_at=datetime(2026, 1, 2, tzinfo=UTC),
            ),
            Member(
                graduation_year=2024,
                real_name="別人",
                institution="Y",
                user_id=other.id,
            ),
        ]
    )
    event = Event(
        title="淨灘",
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


def test_like_then_unlike(ctx):
    client, login, eid = ctx
    login("mem-pw")
    r = client.post(f"/api/events/{eid}/like")
    assert r.status_code == 200
    assert r.json() == {"like_count": 1, "liked": True}

    r = client.request("DELETE", f"/api/events/{eid}/like")
    assert r.json() == {"like_count": 0, "liked": False}


def test_like_is_idempotent(ctx):
    client, login, eid = ctx
    login("mem-pw")
    client.post(f"/api/events/{eid}/like")
    r = client.post(f"/api/events/{eid}/like")
    # Liking twice keeps the count at 1 (unique constraint).
    assert r.json() == {"like_count": 1, "liked": True}


def test_unlike_when_not_liked_is_noop(ctx):
    client, login, eid = ctx
    login("mem-pw")
    r = client.request("DELETE", f"/api/events/{eid}/like")
    assert r.json() == {"like_count": 0, "liked": False}


def test_viewer_cannot_like(ctx):
    client, login, eid = ctx
    login("viewer-pw")
    assert client.post(f"/api/events/{eid}/like").status_code == 403


def test_member_without_profile_cannot_like(ctx):
    client, login, eid = ctx
    login("np-pw")
    assert client.post(f"/api/events/{eid}/like").status_code == 403


def test_like_missing_event_is_404(ctx):
    client, login, _ = ctx
    login("mem-pw")
    assert client.post("/api/events/999999/like").status_code == 404


def test_event_response_carries_like_count_and_liked_by_me(ctx):
    client, login, eid = ctx
    login("mem-pw")
    client.post(f"/api/events/{eid}/like")

    # The liker sees liked_by_me true.
    mine = client.get(f"/api/events/{eid}").json()
    assert mine["like_count"] == 1
    assert mine["liked_by_me"] is True

    # Another member sees the count but liked_by_me false.
    client.post("/api/auth/logout")
    login("other-pw")
    theirs = client.get(f"/api/events/{eid}").json()
    assert theirs["like_count"] == 1
    assert theirs["liked_by_me"] is False


def test_list_likers_shows_who_liked_with_avatar_fields(ctx):
    client, login, eid = ctx
    login("mem-pw")
    client.post(f"/api/events/{eid}/like")

    likers = client.get(f"/api/events/{eid}/likes").json()
    assert len(likers) == 1
    liker = likers[0]
    assert liker["display_name"] == "我本人"
    assert liker["member_id"] is not None
    assert liker["has_photo"] is True
    assert liker["photo_updated_at"] is not None


def test_sort_by_likes_orders_most_hearted_first(ctx):
    client, login, eid = ctx
    # admin creates a second (auto-accepted) event, then members heart the first.
    login("admin-pw")
    eid2 = client.post(
        "/api/events", json={"title": "桌遊", "event_date": "2026-03-02"}
    ).json()["id"]

    client.post("/api/auth/logout")
    login("mem-pw")
    client.post(f"/api/events/{eid}/like")
    client.post("/api/auth/logout")
    login("other-pw")
    client.post(f"/api/events/{eid}/like")

    ids = [
        e["id"] for e in client.get("/api/events?sort=likes&order=desc").json()["items"]
    ]
    # eid has 2 hearts, eid2 has 0 → eid comes first.
    assert ids[0] == eid
    assert ids.index(eid) < ids.index(eid2)
