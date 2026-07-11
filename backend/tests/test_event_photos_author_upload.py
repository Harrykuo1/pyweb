"""An event's author may upload photos to their own event, not just admins.
Mirrors events.py ownership: admin OR the event's author_user_id. Non-author
members stay forbidden.
"""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Event, Member, PostStatus, User, UserRole
from app.routers.event_photos import get_uploads_root

TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000000500010d0a2db40000000049454e44"
    "ae426082"
)


@pytest.fixture
def uploads_dir(tmp_path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def setup(db_session):
    admin = User(username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN)
    author_user = User(password_hash=hash_password("author-pw"), role=UserRole.MEMBER)
    other_user = User(password_hash=hash_password("other-pw"), role=UserRole.MEMBER)
    db_session.add_all([admin, author_user, other_user])
    db_session.commit()
    db_session.add_all(
        [
            Member(graduation_year=2026, real_name="作者", institution="X", user_id=author_user.id),
            Member(graduation_year=2026, real_name="他人", institution="Y", user_id=other_user.id),
        ]
    )
    event = Event(
        title="春酒",
        event_date=date(2026, 3, 1),
        author_user_id=author_user.id,
        status=PostStatus.ACCEPTED,
    )
    db_session.add(event)
    db_session.commit()
    return {"event": event}


@pytest.fixture
def client(db_session, uploads_dir):
    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_uploads_root] = lambda: uploads_dir
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _login(client, pw):
    assert client.post("/api/auth/login", json={"password": pw}).status_code == 200


def _upload(client, event_id):
    files = {"file": ("p.png", TINY_PNG, "image/png")}
    return client.post(f"/api/events/{event_id}/photos", files=files)


def test_author_can_upload_to_own_event(client, setup):
    _login(client, "author-pw")
    r = _upload(client, setup["event"].id)
    assert r.status_code == 201, r.text


def test_non_author_member_forbidden(client, setup):
    _login(client, "other-pw")
    r = _upload(client, setup["event"].id)
    assert r.status_code == 403, r.text


def test_admin_still_can_upload(client, setup):
    _login(client, "admin-pw")
    r = _upload(client, setup["event"].id)
    assert r.status_code == 201, r.text


# ---------- delete / caption: author manages own photos ----------


def _author_uploads(client, event_id):
    _login(client, "author-pw")
    return _upload(client, event_id).json()["id"]


def test_author_can_delete_own_photo_without_password(client, setup):
    eid = setup["event"].id
    pid = _author_uploads(client, eid)
    r = client.request("DELETE", f"/api/events/{eid}/photos/{pid}")
    assert r.status_code == 204, r.text


def test_author_can_edit_own_photo_caption(client, setup):
    eid = setup["event"].id
    pid = _author_uploads(client, eid)
    r = client.put(f"/api/events/{eid}/photos/{pid}", json={"caption": "我的照片"})
    assert r.status_code == 200, r.text
    assert r.json()["caption"] == "我的照片"


def test_non_author_member_cannot_delete_photo(client, setup):
    eid = setup["event"].id
    pid = _author_uploads(client, eid)
    client.post("/api/auth/logout")
    _login(client, "other-pw")
    r = client.request("DELETE", f"/api/events/{eid}/photos/{pid}")
    assert r.status_code == 403, r.text


def test_admin_deleting_photo_still_needs_password(client, setup):
    eid = setup["event"].id
    pid = _author_uploads(client, eid)
    client.post("/api/auth/logout")
    _login(client, "admin-pw")
    assert client.request("DELETE", f"/api/events/{eid}/photos/{pid}").status_code == 422
    r = client.request(
        "DELETE", f"/api/events/{eid}/photos/{pid}", json={"password": "admin-pw"}
    )
    assert r.status_code == 204, r.text
