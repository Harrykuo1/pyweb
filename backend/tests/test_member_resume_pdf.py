from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole
from app.routers.members import get_uploads_root

# Minimal "valid-looking" PDF header bytes — content not actually parsed.
TINY_PDF = b"%PDF-1.4\n%fake\n%%EOF\n"


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


def _seed_pdf_on_disk(
    db_session, uploads_dir: Path, member_id: int = 1, data: bytes = TINY_PDF
) -> Path:
    """Mirror what the upload endpoint persists for an existing resume:
    a file on disk plus the matching path / timestamp columns."""
    relpath = f"members/{member_id}/resume.pdf"
    on_disk = uploads_dir / relpath
    on_disk.parent.mkdir(parents=True, exist_ok=True)
    on_disk.write_bytes(data)
    member = db_session.query(Member).filter_by(id=member_id).one()
    member.resume_pdf_path = relpath
    member.resume_pdf_updated_at = datetime.now(timezone.utc)
    db_session.commit()
    return on_disk


# ---------- upload ----------

def test_upload_pdf_admin(client_factory, db_session, uploads_dir):
    client, login_as = client_factory
    login_as("admin")

    r = client.post(
        "/api/members/1/resume.pdf",
        files={"file": ("a.pdf", TINY_PDF, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_resume_pdf"] is True
    assert body["resume_pdf_updated_at"] is not None

    member = db_session.query(Member).filter_by(id=1).one()
    assert member.resume_pdf_path == "members/1/resume.pdf"
    assert (uploads_dir / member.resume_pdf_path).read_bytes() == TINY_PDF
    assert member.resume_pdf_updated_at is not None


def test_upload_pdf_overwrites_existing(
    client_factory, db_session, uploads_dir
):
    client, login_as = client_factory
    login_as("admin")

    r1 = client.post(
        "/api/members/1/resume.pdf",
        files={"file": ("a.pdf", TINY_PDF, "application/pdf")},
    )
    assert r1.status_code == 200

    new_bytes = b"%PDF-1.4\n%second version\n%%EOF\n"
    r2 = client.post(
        "/api/members/1/resume.pdf",
        files={"file": ("a.pdf", new_bytes, "application/pdf")},
    )
    assert r2.status_code == 200
    member = db_session.query(Member).filter_by(id=1).one()
    assert (uploads_dir / member.resume_pdf_path).read_bytes() == new_bytes
    files = list((uploads_dir / "members" / "1").iterdir())
    assert [p.name for p in files] == ["resume.pdf"]


def test_upload_pdf_bumps_timestamp_on_each_upload(client_factory):
    client, login_as = client_factory
    login_as("admin")

    r1 = client.post(
        "/api/members/1/resume.pdf",
        files={"file": ("a.pdf", TINY_PDF, "application/pdf")},
    )
    first = r1.json()["resume_pdf_updated_at"]
    assert first is not None

    r2 = client.post(
        "/api/members/1/resume.pdf",
        files={"file": ("a.pdf", TINY_PDF, "application/pdf")},
    )
    second = r2.json()["resume_pdf_updated_at"]
    assert second is not None
    assert second >= first


def test_upload_pdf_viewer_403(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.post(
        "/api/members/1/resume.pdf",
        files={"file": ("a.pdf", TINY_PDF, "application/pdf")},
    )
    assert r.status_code == 403


def test_upload_pdf_unauth_401(client_factory):
    client, _ = client_factory
    r = client.post(
        "/api/members/1/resume.pdf",
        files={"file": ("a.pdf", TINY_PDF, "application/pdf")},
    )
    assert r.status_code == 401


def test_upload_pdf_rejects_non_pdf_mime(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/members/1/resume.pdf",
        files={"file": ("a.docx", b"not pdf", "application/msword")},
    )
    assert r.status_code == 415


def test_upload_pdf_rejects_oversized(client_factory):
    client, login_as = client_factory
    login_as("admin")
    big = b"%PDF-1.4\n" + b"\x00" * (10 * 1024 * 1024 + 1)
    r = client.post(
        "/api/members/1/resume.pdf",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert r.status_code == 413


def test_upload_pdf_404(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/members/9999/resume.pdf",
        files={"file": ("a.pdf", TINY_PDF, "application/pdf")},
    )
    assert r.status_code == 404


# ---------- get ----------

def test_get_pdf_returns_bytes(client_factory, db_session, uploads_dir):
    client, login_as = client_factory
    _seed_pdf_on_disk(db_session, uploads_dir)
    login_as("viewer")

    r = client.get("/api/members/1/resume.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "filename" in r.headers["content-disposition"]
    assert r.content == TINY_PDF


def test_get_pdf_sends_nosniff_header(
    client_factory, db_session, uploads_dir
):
    client, login_as = client_factory
    _seed_pdf_on_disk(db_session, uploads_dir)
    login_as("viewer")

    r = client.get("/api/members/1/resume.pdf")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"


def test_get_pdf_response_uses_immutable_cache_header(
    client_factory, db_session, uploads_dir
):
    client, login_as = client_factory
    _seed_pdf_on_disk(db_session, uploads_dir)
    login_as("viewer")

    r = client.get("/api/members/1/resume.pdf")
    assert r.status_code == 200
    cache_control = r.headers.get("cache-control", "")
    assert "private" in cache_control
    assert "max-age=31536000" in cache_control
    assert "immutable" in cache_control


def test_get_pdf_404_when_missing(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/members/1/resume.pdf")
    assert r.status_code == 404


def test_get_pdf_404_when_disk_file_missing(
    client_factory, db_session, uploads_dir
):
    """resume_pdf_path points at a vanished file — surface a 404
    instead of a 500 from FileResponse failing to stat."""
    client, login_as = client_factory
    on_disk = _seed_pdf_on_disk(db_session, uploads_dir)
    on_disk.unlink()
    login_as("viewer")

    r = client.get("/api/members/1/resume.pdf")
    assert r.status_code == 404


def test_get_pdf_unauth_401(client_factory):
    client, _ = client_factory
    r = client.get("/api/members/1/resume.pdf")
    assert r.status_code == 401


# ---------- delete ----------

def test_delete_pdf_admin(client_factory, db_session, uploads_dir):
    client, login_as = client_factory
    on_disk = _seed_pdf_on_disk(db_session, uploads_dir)
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/resume.pdf", json={"password": "admin-pw"},
    )
    assert r.status_code == 204

    member = db_session.query(Member).filter_by(id=1).one()
    db_session.refresh(member)
    assert member.resume_pdf_path is None
    assert member.resume_pdf_updated_at is None
    assert not on_disk.exists()


def test_delete_pdf_removes_empty_member_dir(
    client_factory, db_session, uploads_dir
):
    client, login_as = client_factory
    _seed_pdf_on_disk(db_session, uploads_dir)
    member_dir = uploads_dir / "members" / "1"
    assert member_dir.exists()
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/resume.pdf", json={"password": "admin-pw"},
    )
    assert r.status_code == 204
    assert not member_dir.exists()


def test_delete_pdf_keeps_member_dir_when_photo_remains(
    client_factory, db_session, uploads_dir
):
    """Deleting the resume must leave the per-member directory alone
    when a photo still lives there — the directory only gets reaped
    once both assets are gone."""
    client, login_as = client_factory
    _seed_pdf_on_disk(db_session, uploads_dir)

    photo_path = uploads_dir / "members" / "1" / "photo.png"
    photo_path.write_bytes(b"\x89PNG fake")
    member = db_session.query(Member).filter_by(id=1).one()
    member.photo_path = "members/1/photo.png"
    member.photo_content_type = "image/png"
    member.photo_updated_at = datetime.now(timezone.utc)
    db_session.commit()

    login_as("admin")
    r = client.request(
        "DELETE", "/api/members/1/resume.pdf", json={"password": "admin-pw"},
    )
    assert r.status_code == 204
    assert photo_path.exists()
    assert (uploads_dir / "members" / "1").exists()


def test_delete_pdf_when_disk_file_missing_still_clears_row(
    client_factory, db_session, uploads_dir
):
    client, login_as = client_factory
    on_disk = _seed_pdf_on_disk(db_session, uploads_dir)
    on_disk.unlink()
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/resume.pdf", json={"password": "admin-pw"},
    )
    assert r.status_code == 204
    member = db_session.query(Member).filter_by(id=1).one()
    assert member.resume_pdf_path is None


def test_delete_pdf_wrong_password_returns_422(
    client_factory, db_session, uploads_dir
):
    # See members router helper for why this is 422 instead of 401.
    client, login_as = client_factory
    on_disk = _seed_pdf_on_disk(db_session, uploads_dir)
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/resume.pdf", json={"password": "wrong-pw"},
    )
    assert r.status_code == 422

    member = db_session.query(Member).filter_by(id=1).one()
    assert member.resume_pdf_path == "members/1/resume.pdf"
    assert on_disk.exists()


def test_delete_pdf_missing_password_422(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.delete("/api/members/1/resume.pdf")
    assert r.status_code == 422


def test_delete_pdf_viewer_403(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.request(
        "DELETE", "/api/members/1/resume.pdf", json={"password": "viewer-pw"},
    )
    assert r.status_code == 403
