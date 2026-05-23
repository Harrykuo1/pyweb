from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole
from app.routers.members import get_uploads_root

# Tiny valid PNG (1x1 transparent pixel) to keep payloads cheap.
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
    db_session.add_all([
        User(username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN),
        User(username="viewer", password_hash=hash_password("viewer-pw"), role=UserRole.VIEWER),
    ])
    db_session.add(
        Member(
            id=1,
            graduation_year=2024,
            real_name="Alice",
            institution="SWE",
            joined_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_uploads_root] = lambda: uploads_dir
    client = TestClient(app)

    def login_as(role):
        creds = {"admin": ("admin", "admin-pw"), "viewer": ("viewer", "viewer-pw")}[role]
        r = client.post("/api/auth/login", json={"username": creds[0], "password": creds[1]})
        assert r.status_code == 200, r.text

    try:
        yield client, login_as
    finally:
        client.close()
        app.dependency_overrides.clear()


def _seed_photo_on_disk(
    db_session, uploads_dir: Path, member_id: int = 1,
    *, ext: str = ".png", mime: str = "image/png", data: bytes = TINY_PNG,
) -> Path:
    """Mirror what the upload endpoint persists for an existing photo:
    a file on disk plus the matching path / MIME / timestamp columns."""
    relpath = f"members/{member_id}/photo{ext}"
    on_disk = uploads_dir / relpath
    on_disk.parent.mkdir(parents=True, exist_ok=True)
    on_disk.write_bytes(data)
    member = db_session.query(Member).filter_by(id=member_id).one()
    member.photo_path = relpath
    member.photo_content_type = mime
    member.photo_updated_at = datetime.now(timezone.utc)
    db_session.commit()
    return on_disk


# ---------- upload ----------

def test_upload_photo_admin(client_factory, db_session, uploads_dir):
    client, login_as = client_factory
    login_as("admin")

    r = client.post(
        "/api/members/1/photo",
        files={"file": ("a.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_photo"] is True
    assert body["photo_updated_at"] is not None

    member = db_session.query(Member).filter_by(id=1).one()
    assert member.photo_path == "members/1/photo.png"
    assert (uploads_dir / member.photo_path).read_bytes() == TINY_PNG
    assert member.photo_content_type == "image/png"
    assert member.photo_updated_at is not None


def test_upload_photo_overwrites_same_extension(
    client_factory, db_session, uploads_dir
):
    client, login_as = client_factory
    login_as("admin")

    r1 = client.post(
        "/api/members/1/photo", files={"file": ("a.png", TINY_PNG, "image/png")}
    )
    assert r1.status_code == 200

    # Second upload of a same-extension file just truncates the
    # existing path; no orphan files in the per-member directory.
    new_bytes = TINY_PNG + b"\x00"
    r2 = client.post(
        "/api/members/1/photo", files={"file": ("a.png", new_bytes, "image/png")}
    )
    assert r2.status_code == 200
    member = db_session.query(Member).filter_by(id=1).one()
    assert (uploads_dir / member.photo_path).read_bytes() == new_bytes
    files = list((uploads_dir / "members" / "1").iterdir())
    assert [p.name for p in files] == ["photo.png"]


def test_upload_photo_with_different_extension_removes_old_file(
    client_factory, db_session, uploads_dir
):
    """png -> jpg replacement: the previous on-disk file must be
    deleted, otherwise the member directory leaks stale variants the
    DB no longer references."""
    client, login_as = client_factory
    login_as("admin")

    client.post(
        "/api/members/1/photo", files={"file": ("a.png", TINY_PNG, "image/png")}
    )
    old_path = uploads_dir / "members" / "1" / "photo.png"
    assert old_path.exists()

    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF fake jpeg"
    r = client.post(
        "/api/members/1/photo",
        files={"file": ("b.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert r.status_code == 200

    member = db_session.query(Member).filter_by(id=1).one()
    assert member.photo_path == "members/1/photo.jpg"
    assert not old_path.exists()
    assert (uploads_dir / member.photo_path).read_bytes() == jpeg_bytes


def test_upload_photo_bumps_timestamp_on_each_upload(client_factory):
    client, login_as = client_factory
    login_as("admin")

    r1 = client.post(
        "/api/members/1/photo", files={"file": ("a.png", TINY_PNG, "image/png")}
    )
    first = r1.json()["photo_updated_at"]
    assert first is not None

    r2 = client.post(
        "/api/members/1/photo", files={"file": ("a.png", TINY_PNG, "image/png")}
    )
    second = r2.json()["photo_updated_at"]
    assert second is not None
    assert second >= first


def test_upload_photo_viewer_403(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.post(
        "/api/members/1/photo",
        files={"file": ("a.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 403


def test_upload_photo_unauth_401(client_factory):
    client, _ = client_factory
    r = client.post(
        "/api/members/1/photo",
        files={"file": ("a.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 401


def test_upload_photo_rejects_unsupported_mime(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/members/1/photo",
        files={"file": ("a.gif", b"GIF89a", "image/gif")},
    )
    assert r.status_code == 415


def test_upload_photo_rejects_oversized(client_factory):
    client, login_as = client_factory
    login_as("admin")
    big = b"\x00" * (5 * 1024 * 1024 + 1)
    r = client.post(
        "/api/members/1/photo",
        files={"file": ("big.png", big, "image/png")},
    )
    assert r.status_code == 413


def test_upload_photo_404(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/members/9999/photo",
        files={"file": ("a.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 404


# ---------- get ----------

def test_get_photo_returns_bytes_with_content_type(
    client_factory, db_session, uploads_dir
):
    client, login_as = client_factory
    _seed_photo_on_disk(db_session, uploads_dir)
    login_as("viewer")

    r = client.get("/api/members/1/photo")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == TINY_PNG


def test_get_photo_sends_nosniff_header(
    client_factory, db_session, uploads_dir
):
    # Defence-in-depth: the FS payload is whatever the admin uploaded;
    # nosniff stops browsers from second-guessing the declared MIME
    # and trying to render a hostile upload inline.
    client, login_as = client_factory
    _seed_photo_on_disk(db_session, uploads_dir)
    login_as("viewer")

    r = client.get("/api/members/1/photo")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"


def test_get_photo_response_uses_immutable_cache_header(
    client_factory, db_session, uploads_dir
):
    client, login_as = client_factory
    _seed_photo_on_disk(db_session, uploads_dir)
    login_as("viewer")

    r = client.get("/api/members/1/photo")
    assert r.status_code == 200
    cache_control = r.headers.get("cache-control", "")
    assert "private" in cache_control
    assert "max-age=31536000" in cache_control
    assert "immutable" in cache_control


def test_get_photo_404_when_missing(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/members/1/photo")
    assert r.status_code == 404


def test_get_photo_404_when_disk_file_missing(
    client_factory, db_session, uploads_dir
):
    """photo_path points at a vanished file — surface a 404 instead of
    a 500 from FileResponse failing to stat the missing path."""
    client, login_as = client_factory
    on_disk = _seed_photo_on_disk(db_session, uploads_dir)
    on_disk.unlink()
    login_as("viewer")

    r = client.get("/api/members/1/photo")
    assert r.status_code == 404


def test_get_photo_unauth_401(client_factory):
    client, _ = client_factory
    r = client.get("/api/members/1/photo")
    assert r.status_code == 401


# ---------- delete ----------

def test_delete_photo_admin(client_factory, db_session, uploads_dir):
    client, login_as = client_factory
    on_disk = _seed_photo_on_disk(db_session, uploads_dir)
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/photo", json={"password": "admin-pw"},
    )
    assert r.status_code == 204

    member = db_session.query(Member).filter_by(id=1).one()
    db_session.refresh(member)
    assert member.photo_path is None
    assert member.photo_content_type is None
    assert member.photo_updated_at is None
    assert not on_disk.exists()


def test_delete_photo_removes_empty_member_dir(
    client_factory, db_session, uploads_dir
):
    client, login_as = client_factory
    _seed_photo_on_disk(db_session, uploads_dir)
    member_dir = uploads_dir / "members" / "1"
    assert member_dir.exists()
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/photo", json={"password": "admin-pw"},
    )
    assert r.status_code == 204

    # No resume.pdf alongside the photo, so the per-member directory
    # itself should be reaped — same posture as job_attachments.
    assert not member_dir.exists()


def test_delete_photo_when_disk_file_missing_still_clears_row(
    client_factory, db_session, uploads_dir
):
    client, login_as = client_factory
    on_disk = _seed_photo_on_disk(db_session, uploads_dir)
    on_disk.unlink()
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/photo", json={"password": "admin-pw"},
    )
    assert r.status_code == 204
    member = db_session.query(Member).filter_by(id=1).one()
    assert member.photo_path is None


def test_delete_photo_wrong_password_returns_422(
    client_factory, db_session, uploads_dir
):
    # See members router helper for why this is 422 instead of 401.
    client, login_as = client_factory
    on_disk = _seed_photo_on_disk(db_session, uploads_dir)
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/photo", json={"password": "wrong-pw"},
    )
    assert r.status_code == 422

    member = db_session.query(Member).filter_by(id=1).one()
    assert member.photo_path == "members/1/photo.png"
    assert on_disk.exists()


def test_delete_photo_missing_password_422(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.delete("/api/members/1/photo")
    assert r.status_code == 422


def test_delete_photo_viewer_403(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.request(
        "DELETE", "/api/members/1/photo", json={"password": "viewer-pw"},
    )
    assert r.status_code == 403


def test_delete_photo_404(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.request(
        "DELETE", "/api/members/9999/photo", json={"password": "admin-pw"},
    )
    assert r.status_code == 404
