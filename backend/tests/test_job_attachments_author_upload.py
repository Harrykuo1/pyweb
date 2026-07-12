"""A post's author (the subject member) may upload attachments to their
own job, not just admins. Mirrors the ownership rule already enforced by
jobs.py update/delete: admin OR the job's subject member. Viewers and
non-author members stay forbidden.
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
    """author member (owns the job), a second unrelated member, and admin."""
    admin = User(
        username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN
    )
    author_user = User(password_hash=hash_password("author-pw"), role=UserRole.MEMBER)
    other_user = User(password_hash=hash_password("other-pw"), role=UserRole.MEMBER)
    db_session.add_all([admin, author_user, other_user])
    db_session.commit()

    author_member = Member(
        graduation_year=2026, real_name="作者", institution="X", user_id=author_user.id
    )
    other_member = Member(
        graduation_year=2026, real_name="他人", institution="Y", user_id=other_user.id
    )
    db_session.add_all([author_member, other_member])
    db_session.commit()

    job = Job(
        job_year=2026,
        job_month=5,
        company="Acme",
        kind=JobKind.INTERNSHIP,
        experience_md="hello",
        subject_member_id=author_member.id,
        author_user_id=author_user.id,
        status="accepted",
    )
    db_session.add(job)
    db_session.commit()
    return {"job": job}


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


def _upload(client, job_id):
    files = {"file": ("report.pdf", BytesIO(TINY_PDF), "application/pdf")}
    return client.post(f"/api/jobs/{job_id}/attachments", files=files)


def test_author_can_upload_to_own_job(client, setup):
    _login(client, "author-pw")
    r = _upload(client, setup["job"].id)
    assert r.status_code == 201, r.text


def test_non_author_member_forbidden(client, setup):
    _login(client, "other-pw")
    r = _upload(client, setup["job"].id)
    assert r.status_code == 403, r.text


def test_admin_still_can_upload(client, setup):
    _login(client, "admin-pw")
    r = _upload(client, setup["job"].id)
    assert r.status_code == 201, r.text


# ---------- delete: author manages own attachments ----------


def _author_uploads(client, job_id):
    _login(client, "author-pw")
    aid = _upload(client, job_id).json()["id"]
    return aid


def test_author_can_delete_own_attachment_without_password(client, setup):
    jid = setup["job"].id
    aid = _author_uploads(client, jid)
    # Owner delete needs no admin password (no request body).
    r = client.request("DELETE", f"/api/jobs/{jid}/attachments/{aid}")
    assert r.status_code == 204, r.text


def test_author_can_bulk_delete_own_attachments_without_password(client, setup):
    jid = setup["job"].id
    aid = _author_uploads(client, jid)
    r = client.post(f"/api/jobs/{jid}/attachments/bulk-delete", json={"ids": [aid]})
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] == 1


def test_non_author_member_cannot_delete_attachment(client, setup):
    jid = setup["job"].id
    aid = _author_uploads(client, jid)
    client.post("/api/auth/logout")
    _login(client, "other-pw")
    r = client.request("DELETE", f"/api/jobs/{jid}/attachments/{aid}")
    assert r.status_code == 403, r.text


def test_admin_deleting_attachment_still_needs_password(client, setup):
    jid = setup["job"].id
    aid = _author_uploads(client, jid)
    client.post("/api/auth/logout")
    _login(client, "admin-pw")
    # No password -> rejected.
    assert (
        client.request("DELETE", f"/api/jobs/{jid}/attachments/{aid}").status_code
        == 422
    )
    # Correct password -> deleted.
    r = client.request(
        "DELETE", f"/api/jobs/{jid}/attachments/{aid}", json={"password": "admin-pw"}
    )
    assert r.status_code == 204, r.text
