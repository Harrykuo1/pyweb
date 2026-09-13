from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.media import MediaConversionError
from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import AppConfig, Event, EventPhoto, User, UserRole
from app.routers.event_photos import get_uploads_root

# Tiny valid PNG (1x1 transparent pixel).
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000000500010d0a2db40000000049454e44"
    "ae426082"
)


@pytest.fixture
def uploads_dir(tmp_path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def client_factory(db_session, uploads_dir):
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
    db_session.add(Event(id=1, title="春酒", event_date=date(2026, 3, 1)))
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_uploads_root] = lambda: uploads_dir
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


def _upload(
    client, event_id=1, *, data=TINY_PNG, mime="image/png", name="p.png", caption=None
):
    files = {"file": (name, data, mime)}
    payload = {"caption": caption} if caption is not None else None
    return client.post(f"/api/events/{event_id}/photos", files=files, data=payload)


# ---------- upload ----------


def test_upload_requires_admin(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    assert _upload(client).status_code == 403


def test_upload_stores_file_and_row(client_factory, db_session, uploads_dir):
    client, login_as = client_factory
    login_as("admin")
    r = _upload(client, caption="開心")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["event_id"] == 1
    assert body["caption"] == "開心"
    assert body["filename"] == f"{body['id']}.png"

    on_disk = uploads_dir / "events" / "1" / body["filename"]
    assert on_disk.exists()
    assert on_disk.read_bytes() == TINY_PNG


def test_upload_rejects_non_image(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = _upload(client, data=b"not an image", mime="application/pdf", name="x.pdf")
    assert r.status_code == 415


def test_upload_missing_event_404(client_factory):
    client, login_as = client_factory
    login_as("admin")
    assert _upload(client, event_id=999).status_code == 404


# ---------- list / serve ----------


def test_list_photos_ordered_by_id(client_factory):
    client, login_as = client_factory
    login_as("admin")
    first = _upload(client, name="a.png").json()
    second = _upload(client, name="b.png").json()

    rows = client.get("/api/events/1/photos").json()
    assert [p["id"] for p in rows] == [first["id"], second["id"]]


def test_serve_photo_bytes(client_factory):
    client, login_as = client_factory
    login_as("admin")
    pid = _upload(client).json()["id"]

    # Viewer can read it back.
    login_as("viewer")
    r = client.get(f"/api/events/1/photos/{pid}")
    assert r.status_code == 200
    assert r.content == TINY_PNG
    assert r.headers["content-type"].startswith("image/png")


def test_serve_missing_photo_404(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    assert client.get("/api/events/1/photos/999").status_code == 404


# ---------- caption ----------


def test_update_caption(client_factory):
    client, login_as = client_factory
    login_as("admin")
    pid = _upload(client).json()["id"]

    body = client.put(f"/api/events/1/photos/{pid}", json={"caption": "新說明"}).json()
    assert body["caption"] == "新說明"

    body = client.put(f"/api/events/1/photos/{pid}", json={"caption": "  "}).json()
    assert body["caption"] is None  # blanks normalize to null


# ---------- delete ----------


def test_delete_requires_password(client_factory, db_session, uploads_dir):
    client, login_as = client_factory
    login_as("admin")
    pid = _upload(client).json()["id"]
    on_disk = uploads_dir / "events" / "1" / f"{pid}.png"
    assert on_disk.exists()

    assert (
        client.request(
            "DELETE", f"/api/events/1/photos/{pid}", json={"password": "wrong"}
        ).status_code
        == 422
    )
    assert (
        client.request(
            "DELETE", f"/api/events/1/photos/{pid}", json={"password": "admin-pw"}
        ).status_code
        == 204
    )
    assert not on_disk.exists()
    assert db_session.query(EventPhoto).count() == 0


def test_max_photos_per_event(client_factory, db_session):
    # The cap is admin-tunable now, so the test drives it the same way the
    # settings page would rather than patching a module constant.
    client, login_as = client_factory
    login_as("admin")
    db_session.add(AppConfig(key="max_photos_per_event", value="1"))
    db_session.commit()
    assert _upload(client, name="a.png").status_code == 201
    assert _upload(client, name="b.png").status_code == 409


def test_caption_update_requires_admin(client_factory):
    client, login_as = client_factory
    login_as("admin")
    pid = _upload(client).json()["id"]
    login_as("viewer")
    r = client.put(f"/api/events/1/photos/{pid}", json={"caption": "改說明"})
    assert r.status_code == 403


def test_delete_photo_requires_admin(client_factory, db_session, uploads_dir):
    client, login_as = client_factory
    login_as("admin")
    pid = _upload(client).json()["id"]
    on_disk = uploads_dir / "events" / "1" / f"{pid}.png"
    login_as("viewer")
    r = client.request("DELETE", f"/api/events/1/photos/{pid}", json={"password": "x"})
    assert r.status_code == 403
    assert on_disk.exists()  # viewer cannot delete
    assert db_session.query(EventPhoto).count() == 1


def test_upload_rejects_oversized(client_factory, db_session):
    client, login_as = client_factory
    login_as("admin")
    db_session.add(AppConfig(key="max_photo_mb", value="0"))
    db_session.commit()
    r = _upload(client, data=b"x" * 1024, mime="image/png", name="big.png")
    assert r.status_code == 413


def test_get_photo_isolated_per_event(client_factory, db_session):
    # A photo on event 1 must not be reachable via another event's id —
    # _get_photo_or_404 filters by (id, event_id).
    client, login_as = client_factory
    db_session.add(Event(id=2, title="另一場", event_date=date(2026, 5, 1)))
    db_session.commit()
    login_as("admin")
    pid = _upload(client, event_id=1).json()["id"]
    login_as("viewer")
    assert client.get(f"/api/events/2/photos/{pid}").status_code == 404
    assert client.get(f"/api/events/1/photos/{pid}").status_code == 200


def test_rejected_photo_leaves_no_file_and_no_row(
    client_factory, db_session, uploads_dir
):
    """The row is flushed before the bytes land, so the id can name the file.

    An over-limit upload therefore has to unwind both: the session is never
    committed, and the partial file is removed — otherwise a rejected upload
    would leave an orphan row pointing at nothing, or a stub on disk.
    """
    client, login_as = client_factory
    login_as("admin")
    db_session.add(AppConfig(key="max_photo_mb", value="0"))
    db_session.commit()
    r = _upload(client, data=b"x" * 1024, mime="image/png", name="big.png")
    assert r.status_code == 413

    assert db_session.query(EventPhoto).count() == 0
    event_dir = uploads_dir / "events" / "1"
    leftovers = list(event_dir.iterdir()) if event_dir.exists() else []
    assert leftovers == [], leftovers


def test_upload_records_the_streamed_byte_count(client_factory, uploads_dir):
    # size_bytes is backfilled from the stream rather than len(data), so it
    # has to still match what actually reached the disk.
    client, login_as = client_factory
    login_as("admin")
    payload = b"\x89PNG\r\n\x1a\n" + b"z" * 5000
    body = _upload(client, data=payload, mime="image/png", name="sized.png").json()

    assert body["size_bytes"] == len(payload)
    on_disk = uploads_dir / "events" / "1" / body["filename"]
    assert on_disk.stat().st_size == len(payload)


def test_photo_limits_follow_runtime_config(client_factory, db_session):
    """The caps used to be module constants, so an admin could not touch
    them without a rebuild. Prove both now read from app_configs."""
    client, login_as = client_factory
    login_as("admin")

    db_session.add(AppConfig(key="max_photo_mb", value="1"))
    db_session.commit()
    under = b"\x89PNG\r\n\x1a\n" + b"z" * 1000
    assert (
        _upload(client, data=under, mime="image/png", name="ok.png").status_code == 201
    )

    over = b"\x89PNG\r\n\x1a\n" + b"z" * (1024 * 1024 + 1)
    r = _upload(client, data=over, mime="image/png", name="big.png")
    assert r.status_code == 413
    assert "1 MB" in r.json()["detail"]


def test_heic_upload_is_stored_as_jpeg(
    client_factory, db_session, uploads_dir, monkeypatch
):
    """iPhones shoot HEIC by default and no browser renders it, so the upload
    is converted rather than stored as shot. The row has to report the
    converted type — a stored image/heic would tell the frontend to render
    something it cannot."""
    client, login_as = client_factory
    login_as("admin")

    def fake_convert(source, target):
        # ffmpeg reads the staged upload, never the destination.
        assert source.exists() and source != target
        target.write_bytes(b"\xff\xd8\xff" + b"j" * 200)

    monkeypatch.setattr("app.routers.event_photos.heic_to_jpeg", fake_convert)

    body = _upload(
        client, data=b"heic-bytes", mime="image/heic", name="IMG_0001.HEIC"
    ).json()

    assert body["mime_type"] == "image/jpeg"
    assert body["filename"].endswith(".jpg")

    event_dir = uploads_dir / "events" / "1"
    stored = event_dir / body["filename"]
    assert stored.exists()
    # size_bytes tracks what was stored, not what arrived.
    assert body["size_bytes"] == stored.stat().st_size
    # The staging file must not outlive the conversion.
    assert list(event_dir.iterdir()) == [stored]


def test_undecodable_heic_is_rejected_not_stored(
    client_factory, db_session, uploads_dir, monkeypatch
):
    # Keeping the original would turn a failed conversion into a broken image
    # on the event page later, which is much harder to trace than a refusal.
    client, login_as = client_factory
    login_as("admin")

    def boom(source, target):
        raise MediaConversionError("invalid data found when processing input")

    monkeypatch.setattr("app.routers.event_photos.heic_to_jpeg", boom)

    r = _upload(client, data=b"not really heic", mime="image/heic", name="bad.heic")
    assert r.status_code == 415

    assert db_session.query(EventPhoto).count() == 0
    event_dir = uploads_dir / "events" / "1"
    leftovers = list(event_dir.iterdir()) if event_dir.exists() else []
    assert leftovers == [], leftovers
