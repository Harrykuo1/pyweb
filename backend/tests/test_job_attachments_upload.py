from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import AppConfig, Job, JobAttachment, JobKind, User, UserRole
from app.routers.job_attachments import get_uploads_root


# A minimal but real PDF byte string so MIME inspection downstream
# stays plausible. The shape doesn't have to validate as PDF — the
# router only checks the Content-Type header and extension.
TINY_PDF = b"%PDF-1.4\n%\xc4\xe5\xf2\xe5\xeb\xa7\xf3\xa0\xd0\xc4\xc6\n"


@pytest.fixture
def uploads_dir(tmp_path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def job(db_session) -> Job:
    job = Job(
        job_year=2026,
        job_month=5,
        company="Acme",
        kind=JobKind.INTERNSHIP,
        experience_md="hello",
    )
    db_session.add(job)
    db_session.commit()
    return job


@pytest.fixture
def client(db_session, uploads_dir):
    db_session.add_all([
        User(username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN),
        User(username="viewer", password_hash=hash_password("viewer-pw"), role=UserRole.VIEWER),
    ])
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_uploads_root] = lambda: uploads_dir
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _login_admin(client):
    assert client.post("/api/auth/login", json={"password": "admin-pw"}).status_code == 200


def _login_viewer(client):
    assert client.post("/api/auth/login", json={"password": "viewer-pw"}).status_code == 200


def _upload(client, job_id, *, filename="report.pdf", body=TINY_PDF, mime="application/pdf", strategy=None):
    files = {"file": (filename, BytesIO(body), mime)}
    data = {}
    if strategy is not None:
        data["conflict_strategy"] = strategy
    return client.post(f"/api/jobs/{job_id}/attachments", files=files, data=data)


# ---------- Permissions ----------


def test_upload_requires_admin(client, job):
    r = _upload(client, job.id)
    assert r.status_code == 401


def test_upload_viewer_forbidden(client, job):
    _login_viewer(client)
    r = _upload(client, job.id)
    assert r.status_code == 403


# ---------- Happy path ----------


def test_upload_admin_success_stores_row_and_file(client, job, db_session, uploads_dir):
    _login_admin(client)
    r = _upload(client, job.id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["job_id"] == job.id
    assert body["filename"] == "report.pdf"
    assert body["mime_type"] == "application/pdf"
    assert body["size_bytes"] == len(TINY_PDF)

    rows = db_session.query(JobAttachment).filter_by(job_id=job.id).all()
    assert len(rows) == 1
    assert rows[0].filename == "report.pdf"

    on_disk = uploads_dir / "jobs" / str(job.id) / "report.pdf"
    assert on_disk.exists()
    assert on_disk.read_bytes() == TINY_PDF


# ---------- Validation ----------


def test_upload_unknown_job_404(client):
    _login_admin(client)
    r = _upload(client, 9999)
    assert r.status_code == 404


def test_upload_rejects_disallowed_extension(client, job):
    _login_admin(client)
    r = _upload(
        client,
        job.id,
        filename="evil.exe",
        body=b"MZ\x90\x00",
        mime="application/octet-stream",
    )
    assert r.status_code == 415


def test_upload_rejects_disallowed_mime(client, job):
    _login_admin(client)
    # Extension is fine, but the Content-Type lies about it.
    r = _upload(
        client,
        job.id,
        filename="report.pdf",
        body=TINY_PDF,
        mime="application/octet-stream",
    )
    assert r.status_code == 415


def test_upload_rejects_oversized(client, job, db_session):
    # Tighten the size limit to 1 byte so the tiny PDF blows past it.
    db_session.add(AppConfig(key="max_attachment_mb", value="0"))
    db_session.commit()

    _login_admin(client)
    r = _upload(client, job.id)
    # max_attachment_mb=0 means max_bytes=0; the body is non-empty so 413.
    assert r.status_code == 413


def test_upload_rejects_path_traversal_filename(client, job):
    _login_admin(client)
    files = {"file": ("../../etc/passwd", BytesIO(TINY_PDF), "application/pdf")}
    r = client.post(f"/api/jobs/{job.id}/attachments", files=files)
    # Sanitization strips the path components down to "passwd", which has
    # no allowed extension and gets rejected at the extension check.
    assert r.status_code == 415


def test_upload_respects_max_attachments_per_job(client, job, db_session):
    # Pinch the limit down so the second upload trips the cap.
    db_session.add(AppConfig(key="max_attachments_per_job", value="1"))
    db_session.commit()

    _login_admin(client)
    r1 = _upload(client, job.id, filename="a.pdf")
    assert r1.status_code == 201
    r2 = _upload(client, job.id, filename="b.pdf")
    assert r2.status_code == 409
    assert "上限" in r2.json()["detail"]


# ---------- Conflict handling ----------


def test_upload_conflict_without_strategy_returns_409(client, job, uploads_dir):
    _login_admin(client)
    _upload(client, job.id, filename="report.pdf")
    r = _upload(client, job.id, filename="report.pdf")
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["error"] == "filename_conflict"
    assert detail["conflicting_filename"] == "report.pdf"


def test_upload_conflict_with_rename_appends_suffix(client, job, db_session, uploads_dir):
    _login_admin(client)
    _upload(client, job.id, filename="report.pdf")
    r = _upload(client, job.id, filename="report.pdf", strategy="rename")
    assert r.status_code == 201
    assert r.json()["filename"] == "report (1).pdf"

    rows = (
        db_session.query(JobAttachment)
        .filter_by(job_id=job.id)
        .order_by(JobAttachment.id)
        .all()
    )
    assert [row.filename for row in rows] == ["report.pdf", "report (1).pdf"]
    assert (uploads_dir / "jobs" / str(job.id) / "report (1).pdf").exists()


def test_upload_rename_keeps_climbing_on_repeated_conflicts(client, job, uploads_dir):
    _login_admin(client)
    _upload(client, job.id, filename="report.pdf")
    _upload(client, job.id, filename="report.pdf", strategy="rename")
    r = _upload(client, job.id, filename="report.pdf", strategy="rename")
    assert r.status_code == 201
    assert r.json()["filename"] == "report (2).pdf"


def test_upload_conflict_with_overwrite_replaces_in_place(client, job, db_session, uploads_dir):
    _login_admin(client)
    first = _upload(client, job.id, filename="report.pdf")
    original_id = first.json()["id"]
    original_path = uploads_dir / "jobs" / str(job.id) / "report.pdf"
    assert original_path.read_bytes() == TINY_PDF

    new_body = b"%PDF-1.7\n%new\n"
    r = _upload(client, job.id, filename="report.pdf", body=new_body, strategy="overwrite")
    assert r.status_code == 201
    # Same row ID, new size.
    assert r.json()["id"] == original_id
    assert r.json()["size_bytes"] == len(new_body)

    rows = db_session.query(JobAttachment).filter_by(job_id=job.id).all()
    assert len(rows) == 1
    assert original_path.read_bytes() == new_body


def test_overwrite_does_not_trigger_count_limit(client, job, db_session):
    """Overwrite reuses the existing row, so it must not be blocked by
    the per-job attachment count even when we're already at the cap."""
    db_session.add(AppConfig(key="max_attachments_per_job", value="1"))
    db_session.commit()

    _login_admin(client)
    _upload(client, job.id, filename="report.pdf")
    r = _upload(client, job.id, filename="report.pdf", strategy="overwrite")
    assert r.status_code == 201
