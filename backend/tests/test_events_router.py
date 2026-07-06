from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Event, EventPhoto, EventTag, PostStatus, User, UserRole


@pytest.fixture
def client_factory(db_session):
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
    client = TestClient(app)

    def login_as(role):
        creds = {"admin": ("admin", "admin-pw"), "viewer": ("viewer", "viewer-pw")}[
            role
        ]
        r = client.post(
            "/api/auth/login", json={"username": creds[0], "password": creds[1]}
        )
        assert r.status_code == 200, r.text

    try:
        yield client, login_as
    finally:
        client.close()
        app.dependency_overrides.clear()


def _seed_event(
    db_session, *, title, event_date, tags=(), location=None, created_day=1
):
    ev = Event(
        title=title,
        event_date=event_date,
        location=location,
        status=PostStatus.ACCEPTED,
        created_at=datetime(2025, 1, created_day, tzinfo=UTC),
    )
    for name in tags:
        ev.tags.append(EventTag(name=name))
    db_session.add(ev)
    db_session.commit()
    return ev


# ---------- auth ----------


def test_list_requires_auth(client_factory):
    client, _ = client_factory
    assert client.get("/api/events").status_code == 401


def test_create_requires_admin(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.post("/api/events", json={"title": "x", "event_date": "2026-03-01"})
    assert r.status_code == 403


# ---------- create / read ----------


def test_create_event_with_tags(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/events",
        json={
            "title": "春酒聚餐",
            "event_date": "2026-03-15",
            "location": "台北",
            "description_md": "# 很開心",
            "tags": ["春酒", "聚餐", "春酒"],  # dup collapses
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "春酒聚餐"
    assert body["event_date"] == "2026-03-15"
    assert body["tags"] == ["春酒", "聚餐"]
    assert body["photo_count"] == 0
    assert body["cover_photo_id"] is None


def test_get_event_includes_photo_aggregates(client_factory, db_session):
    client, login_as = client_factory
    ev = _seed_event(db_session, title="比賽", event_date=date(2026, 2, 1))
    db_session.add_all(
        [
            EventPhoto(
                event_id=ev.id, filename="x.jpg", mime_type="image/jpeg", size_bytes=1
            ),
            EventPhoto(
                event_id=ev.id, filename="y.jpg", mime_type="image/jpeg", size_bytes=1
            ),
        ]
    )
    db_session.commit()
    cover_id = (
        db_session.query(EventPhoto)
        .filter_by(event_id=ev.id)
        .order_by(EventPhoto.id)
        .first()
        .id
    )
    login_as("viewer")

    body = client.get(f"/api/events/{ev.id}").json()
    assert body["photo_count"] == 2
    assert body["cover_photo_id"] == cover_id


def test_get_missing_event_404(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    assert client.get("/api/events/999").status_code == 404


# ---------- sort / filter / search ----------


def test_list_default_sort_event_date_desc(client_factory, db_session):
    client, login_as = client_factory
    _seed_event(db_session, title="舊", event_date=date(2025, 1, 1))
    _seed_event(db_session, title="新", event_date=date(2026, 6, 1))
    _seed_event(db_session, title="中", event_date=date(2025, 9, 1))
    login_as("viewer")

    items = client.get("/api/events").json()["items"]
    assert [e["title"] for e in items] == ["新", "中", "舊"]


def test_list_sort_event_date_asc(client_factory, db_session):
    client, login_as = client_factory
    _seed_event(db_session, title="舊", event_date=date(2025, 1, 1))
    _seed_event(db_session, title="新", event_date=date(2026, 6, 1))
    login_as("viewer")

    items = client.get("/api/events?order=asc").json()["items"]
    assert [e["title"] for e in items] == ["舊", "新"]


def test_list_filter_by_year(client_factory, db_session):
    client, login_as = client_factory
    _seed_event(db_session, title="2025場", event_date=date(2025, 5, 1))
    _seed_event(db_session, title="2026場", event_date=date(2026, 5, 1))
    login_as("viewer")

    items = client.get("/api/events?year=2026").json()["items"]
    assert [e["title"] for e in items] == ["2026場"]


def test_list_filter_by_tag_or_matches(client_factory, db_session):
    client, login_as = client_factory
    _seed_event(db_session, title="A", event_date=date(2026, 1, 1), tags=["聚餐"])
    _seed_event(db_session, title="B", event_date=date(2026, 2, 1), tags=["比賽"])
    _seed_event(
        db_session, title="C", event_date=date(2026, 3, 1), tags=["出遊", "聚餐"]
    )
    login_as("viewer")

    titles = {e["title"] for e in client.get("/api/events?tag=聚餐").json()["items"]}
    assert titles == {"A", "C"}


def test_list_tag_filter_no_duplicate_rows(client_factory, db_session):
    # An event matching multiple selected tags must appear once, not per tag.
    client, login_as = client_factory
    _seed_event(
        db_session, title="C", event_date=date(2026, 3, 1), tags=["出遊", "聚餐"]
    )
    login_as("viewer")

    body = client.get("/api/events?tag=出遊&tag=聚餐").json()
    assert body["total"] == 1


def test_list_search_matches_title_and_location(client_factory, db_session):
    client, login_as = client_factory
    _seed_event(db_session, title="桌遊之夜", event_date=date(2026, 1, 1))
    _seed_event(
        db_session, title="爬山", event_date=date(2026, 2, 1), location="陽明山"
    )
    login_as("viewer")

    titles = {e["title"] for e in client.get("/api/events?q=桌遊").json()["items"]}
    assert titles == {"桌遊之夜"}
    titles = {e["title"] for e in client.get("/api/events?q=陽明山").json()["items"]}
    assert titles == {"爬山"}


def test_tags_endpoint_returns_distinct_sorted(client_factory, db_session):
    client, login_as = client_factory
    _seed_event(
        db_session, title="A", event_date=date(2026, 1, 1), tags=["聚餐", "出遊"]
    )
    _seed_event(db_session, title="B", event_date=date(2026, 2, 1), tags=["聚餐"])
    login_as("viewer")

    tags = client.get("/api/events/tags").json()
    assert tags == sorted(["出遊", "聚餐"])


# ---------- update ----------


def test_update_replaces_tags(client_factory, db_session):
    client, login_as = client_factory
    ev = _seed_event(
        db_session, title="A", event_date=date(2026, 1, 1), tags=["舊標籤"]
    )
    login_as("admin")

    body = client.put(
        f"/api/events/{ev.id}", json={"tags": ["新標籤", "另一個"]}
    ).json()
    assert body["tags"] == ["另一個", "新標籤"]  # response sorted by name


def test_update_partial_keeps_other_fields(client_factory, db_session):
    client, login_as = client_factory
    ev = _seed_event(
        db_session, title="原標題", event_date=date(2026, 1, 1), tags=["t"]
    )
    login_as("admin")

    body = client.put(f"/api/events/{ev.id}", json={"title": "新標題"}).json()
    assert body["title"] == "新標題"
    assert body["tags"] == ["t"]  # untouched when tags omitted


# ---------- delete ----------


def test_delete_requires_correct_password(client_factory, db_session):
    client, login_as = client_factory
    ev = _seed_event(db_session, title="A", event_date=date(2026, 1, 1))
    login_as("admin")

    assert (
        client.request(
            "DELETE", f"/api/events/{ev.id}", json={"password": "wrong"}
        ).status_code
        == 422
    )
    assert (
        client.request(
            "DELETE", f"/api/events/{ev.id}", json={"password": "admin-pw"}
        ).status_code
        == 204
    )
    assert db_session.query(Event).count() == 0


def test_delete_cascades_tags(client_factory, db_session):
    client, login_as = client_factory
    ev = _seed_event(
        db_session, title="A", event_date=date(2026, 1, 1), tags=["x", "y"]
    )
    login_as("admin")

    client.request("DELETE", f"/api/events/{ev.id}", json={"password": "admin-pw"})
    assert db_session.query(EventTag).count() == 0


def test_update_requires_admin(client_factory, db_session):
    client, login_as = client_factory
    ev = _seed_event(db_session, title="A", event_date=date(2026, 1, 1))
    login_as("viewer")
    r = client.put(f"/api/events/{ev.id}", json={"title": "新"})
    assert r.status_code == 403


def test_delete_requires_admin(client_factory, db_session):
    client, login_as = client_factory
    ev = _seed_event(db_session, title="A", event_date=date(2026, 1, 1))
    login_as("viewer")
    # Valid-shaped body so the request reaches require_admin, not 422.
    r = client.request("DELETE", f"/api/events/{ev.id}", json={"password": "x"})
    assert r.status_code == 403
    assert db_session.query(Event).count() == 1  # nothing deleted
