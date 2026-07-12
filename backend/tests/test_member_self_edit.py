from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole
from app.routers.members import get_uploads_root

# Tiny valid PNG (1x1 transparent pixel).
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000000500010d0a2db40000000049454e44"
    "ae426082"
)
TINY_PDF = b"%PDF-1.4\n%stub\n"


@pytest.fixture
def uploads_dir(tmp_path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def client(db_session, uploads_dir):
    # admin + two member accounts, each owning its own profile. Login is by
    # password alone (linear scan over users), so each needs a distinct one.
    admin = User(
        username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN
    )
    m1 = User(username="m1", password_hash=hash_password("m1-pw"), role=UserRole.MEMBER)
    m2 = User(username="m2", password_hash=hash_password("m2-pw"), role=UserRole.MEMBER)
    db_session.add_all([admin, m1, m2])
    db_session.flush()
    db_session.add(
        Member(
            id=1,
            user_id=m1.id,
            graduation_year=2024,
            real_name="Mine",
            institution="X",
            joined_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )
    db_session.add(
        Member(
            id=2,
            user_id=m2.id,
            graduation_year=2024,
            real_name="Theirs",
            institution="Y",
            joined_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_uploads_root] = lambda: uploads_dir
    client = TestClient(app)

    def login(pw):
        assert client.post("/api/auth/login", json={"password": pw}).status_code == 200

    try:
        yield client, login
    finally:
        client.close()
        app.dependency_overrides.clear()


# ---------- profile fields (PUT) ----------


def test_member_updates_own_profile(client):
    c, login = client
    login("m1-pw")
    r = c.put("/api/members/1", json={"institution": "New Corp", "position": "SWE"})
    assert r.status_code == 200, r.text
    assert r.json()["institution"] == "New Corp"
    assert r.json()["position"] == "SWE"


def test_member_cannot_update_others_profile(client):
    c, login = client
    login("m1-pw")
    r = c.put("/api/members/2", json={"real_name": "Hijack"})
    assert r.status_code == 403


def test_member_update_silently_ignores_joined_at(client):
    c, login = client
    login("m1-pw")
    r = c.put(
        "/api/members/1",
        json={"joined_at": "1999-01-01T00:00:00Z", "position": "PM"},
    )
    assert r.status_code == 200
    # joined_at is dropped for non-admins; the rest of the patch still lands.
    assert r.json()["joined_at"].startswith("2024-01-01")
    assert r.json()["position"] == "PM"


def test_admin_can_update_any_member_including_joined_at(client):
    c, login = client
    login("admin-pw")
    r = c.put("/api/members/1", json={"joined_at": "2000-05-05T00:00:00Z"})
    assert r.status_code == 200
    assert r.json()["joined_at"].startswith("2000-05-05")


# ---------- photo ----------


def test_member_uploads_and_deletes_own_photo_without_password(client):
    c, login = client
    login("m1-pw")
    up = c.post(
        "/api/members/1/photo", files={"file": ("p.png", TINY_PNG, "image/png")}
    )
    assert up.status_code == 200, up.text
    assert up.json()["has_photo"] is True
    # Owner deletes their own photo without a password confirmation.
    assert c.delete("/api/members/1/photo").status_code == 204


def test_member_cannot_upload_others_photo(client):
    c, login = client
    login("m1-pw")
    r = c.post("/api/members/2/photo", files={"file": ("p.png", TINY_PNG, "image/png")})
    assert r.status_code == 403


def test_admin_delete_photo_still_requires_password(client):
    c, login = client
    login("m1-pw")
    assert (
        c.post(
            "/api/members/1/photo", files={"file": ("p.png", TINY_PNG, "image/png")}
        ).status_code
        == 200
    )
    login("admin-pw")
    assert c.delete("/api/members/1/photo").status_code == 422  # no confirmation
    assert (
        c.request(
            "DELETE", "/api/members/1/photo", json={"password": "nope"}
        ).status_code
        == 422
    )
    assert (
        c.request(
            "DELETE", "/api/members/1/photo", json={"password": "admin-pw"}
        ).status_code
        == 204
    )


# ---------- resume pdf ----------


def test_member_uploads_and_deletes_own_resume_pdf_without_password(client):
    c, login = client
    login("m1-pw")
    up = c.post(
        "/api/members/1/resume.pdf",
        files={"file": ("r.pdf", TINY_PDF, "application/pdf")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["has_resume_pdf"] is True
    assert c.delete("/api/members/1/resume.pdf").status_code == 204


def test_member_cannot_upload_others_resume_pdf(client):
    c, login = client
    login("m1-pw")
    r = c.post(
        "/api/members/2/resume.pdf",
        files={"file": ("r.pdf", TINY_PDF, "application/pdf")},
    )
    assert r.status_code == 403
