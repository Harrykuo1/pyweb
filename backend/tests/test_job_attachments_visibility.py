"""Attachment reads must honor post visibility the same way jobs.get_job
does: a non-admin who is not the post's subject owner must NOT reach the
attachments of a non-accepted (pending/rejected) post — the post body 404s
for them, so its files must too. Accepted posts stay readable by any member
(per product decision, that includes accepted anonymous posts).
"""

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Job, JobKind, Member, User, UserRole
from app.routers.job_attachments import get_uploads_root

TINY_PDF = b"%PDF-1.4\n%\xc4\xe5\xf2\xe5\xeb\xa7\xf3\xa0\xd0\xc4\xc6\n"


@pytest.fixture
def uploads_dir(tmp_path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def setup(db_session):
    admin = User(username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN)
    author_user = User(password_hash=hash_password("author-pw"), role=UserRole.MEMBER)
    other_user = User(password_hash=hash_password("other-pw"), role=UserRole.MEMBER)
    viewer_user = User(username="viewer", password_hash=hash_password("viewer-pw"), role=UserRole.VIEWER)
    db_session.add_all([admin, author_user, other_user, viewer_user])
    db_session.commit()

    author_member = Member(
        graduation_year=2026, real_name="作者", institution="X", user_id=author_user.id
    )
    other_member = Member(
        graduation_year=2026, real_name="他人", institution="Y", user_id=other_user.id
    )
    db_session.add_all([author_member, other_member])
    db_session.commit()

    def _job(status: str) -> Job:
        return Job(
            job_year=2026,
            job_month=5,
            company="Acme",
            kind=JobKind.INTERNSHIP,
            experience_md="hello",
            subject_member_id=author_member.id,
            author_user_id=author_user.id,
            status=status,
        )

    pending = _job("pending")
    accepted = _job("accepted")
    db_session.add_all([pending, accepted])
    db_session.commit()
    return {"pending": pending, "accepted": accepted}


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


def _author_upload(client, job_id) -> int:
    """Author uploads a real attachment (file + DB row), then logs out."""
    _login(client, "author-pw")
    files = {"file": ("report.pdf", BytesIO(TINY_PDF), "application/pdf")}
    aid = client.post(f"/api/jobs/{job_id}/attachments", files=files).json()["id"]
    client.post("/api/auth/logout")
    return aid


# ---------- pending post: attachments hidden from non-owner non-admin ----------


@pytest.mark.parametrize("pw", ["other-pw", "viewer-pw"])
def test_non_owner_cannot_list_pending_attachments(client, setup, pw):
    jid = setup["pending"].id
    _author_upload(client, jid)
    _login(client, pw)
    assert client.get(f"/api/jobs/{jid}/attachments").status_code == 404


@pytest.mark.parametrize("pw", ["other-pw", "viewer-pw"])
def test_non_owner_cannot_download_pending_attachment(client, setup, pw):
    jid = setup["pending"].id
    aid = _author_upload(client, jid)
    _login(client, pw)
    assert client.get(f"/api/jobs/{jid}/attachments/{aid}").status_code == 404


@pytest.mark.parametrize("pw", ["other-pw", "viewer-pw"])
def test_non_owner_cannot_preview_pending_attachment(client, setup, pw):
    jid = setup["pending"].id
    aid = _author_upload(client, jid)
    _login(client, pw)
    assert client.get(f"/api/jobs/{jid}/attachments/{aid}/preview").status_code == 404


@pytest.mark.parametrize("pw", ["other-pw", "viewer-pw"])
def test_non_owner_cannot_bulk_download_pending_attachments(client, setup, pw):
    jid = setup["pending"].id
    aid = _author_upload(client, jid)
    _login(client, pw)
    r = client.post(f"/api/jobs/{jid}/attachments/bulk-download", json={"ids": [aid]})
    assert r.status_code == 404


# ---------- owner + admin keep full access to a pending post's attachments ----------


def test_owner_can_list_own_pending_attachments(client, setup):
    jid = setup["pending"].id
    _author_upload(client, jid)
    _login(client, "author-pw")
    assert client.get(f"/api/jobs/{jid}/attachments").status_code == 200


def test_admin_can_list_pending_attachments(client, setup):
    jid = setup["pending"].id
    _author_upload(client, jid)
    _login(client, "admin-pw")
    assert client.get(f"/api/jobs/{jid}/attachments").status_code == 200


# ---------- accepted post: attachments stay visible to any member/viewer ----------


@pytest.mark.parametrize("pw", ["other-pw", "viewer-pw"])
def test_accepted_post_attachments_visible_to_everyone(client, setup, pw):
    jid = setup["accepted"].id
    _author_upload(client, jid)
    _login(client, pw)
    assert client.get(f"/api/jobs/{jid}/attachments").status_code == 200
