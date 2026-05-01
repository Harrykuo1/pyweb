from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole

# Minimal "valid-looking" PDF header bytes — content not actually parsed.
TINY_PDF = b"%PDF-1.4\n%fake\n%%EOF\n"


@pytest.fixture
def client_factory(db_session):
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


# ---------- upload ----------

def test_upload_pdf_admin(client_factory, db_session):
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
    assert member.resume_pdf == TINY_PDF
    assert member.resume_pdf_updated_at is not None


def test_upload_pdf_bumps_timestamp_on_each_upload(client_factory, db_session):
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

def test_get_pdf_returns_bytes(client_factory, db_session):
    client, login_as = client_factory
    member = db_session.query(Member).filter_by(id=1).one()
    member.resume_pdf = TINY_PDF
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/members/1/resume.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "filename" in r.headers["content-disposition"]
    assert r.content == TINY_PDF


def test_get_pdf_response_uses_immutable_cache_header(client_factory, db_session):
    # See the photo equivalent test for rationale — same content-
    # addressed-URL guarantee via ?v=<resume_pdf_updated_at>.
    client, login_as = client_factory
    member = db_session.query(Member).filter_by(id=1).one()
    member.resume_pdf = TINY_PDF
    db_session.commit()
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


def test_get_pdf_unauth_401(client_factory):
    client, _ = client_factory
    r = client.get("/api/members/1/resume.pdf")
    assert r.status_code == 401


# ---------- delete ----------

def test_delete_pdf_admin(client_factory, db_session):
    client, login_as = client_factory
    member = db_session.query(Member).filter_by(id=1).one()
    member.resume_pdf = TINY_PDF
    member.resume_pdf_updated_at = datetime.now(timezone.utc)
    db_session.commit()
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/resume.pdf", json={"password": "admin-pw"},
    )
    assert r.status_code == 204

    db_session.refresh(member)
    assert member.resume_pdf is None
    assert member.resume_pdf_updated_at is None


def test_delete_pdf_wrong_password_401(client_factory, db_session):
    client, login_as = client_factory
    member = db_session.query(Member).filter_by(id=1).one()
    member.resume_pdf = TINY_PDF
    db_session.commit()
    login_as("admin")

    r = client.request(
        "DELETE", "/api/members/1/resume.pdf", json={"password": "wrong-pw"},
    )
    assert r.status_code == 401

    db_session.refresh(member)
    assert member.resume_pdf == TINY_PDF


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
