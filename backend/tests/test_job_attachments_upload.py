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
    app.dependency_overrides[get_uploads_root] = lambda: uploads_dir
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _login_admin(client):
    assert (
        client.post("/api/auth/login", json={"password": "admin-pw"}).status_code == 200
    )


def _login_viewer(client):
    assert (
        client.post("/api/auth/login", json={"password": "viewer-pw"}).status_code
        == 200
    )


def _upload(
    client,
    job_id,
    *,
    filename="report.pdf",
    body=TINY_PDF,
    mime="application/pdf",
    strategy=None,
):
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


def test_upload_accepts_zip_archive(client, job, db_session):
    """Archives are stored as opaque blobs — no preview, just download.
    This guards the allowlist so a future tweak doesn't quietly drop
    the file types users have come to rely on."""
    _login_admin(client)
    r = _upload(
        client,
        job.id,
        filename="bundle.zip",
        body=b"PK\x03\x04 fake zip body",
        mime="application/zip",
    )
    assert r.status_code == 201, r.text


def test_upload_accepts_octet_stream_archive(client, job):
    """Some browsers can't identify rar/7z by MIME and fall back to
    application/octet-stream. The extension allowlist is the real
    gate, so we accept the fallback rather than 415ing the user."""
    _login_admin(client)
    r = _upload(
        client,
        job.id,
        filename="bundle.7z",
        body=b"7z\xbc\xaf\x27\x1c fake",
        mime="application/octet-stream",
    )
    assert r.status_code == 201, r.text


# ---------- Validation ----------


def test_upload_unknown_job_404(client):
    _login_admin(client)
    r = _upload(client, 9999)
    assert r.status_code == 404


def test_upload_accepts_arbitrary_extension(client, job):
    """No extension allowlist: any byte payload the admin uploads is
    stored as-is. The download endpoint takes responsibility for
    serving non-previewable types as attachments so this can't turn
    into an XSS vector."""
    _login_admin(client)
    r = _upload(
        client,
        job.id,
        filename="random.weirdext",
        body=b"some content",
        mime="application/octet-stream",
    )
    assert r.status_code == 201


def test_upload_accepts_arbitrary_mime(client, job):
    """MIME is advisory only — even text/plain on a .pdf goes through.
    The decision of "render inline vs force-download" is made at
    serve time based on the extension, not the MIME the client
    asserted at upload."""
    _login_admin(client)
    r = _upload(
        client,
        job.id,
        filename="report.pdf",
        body=TINY_PDF,
        mime="text/plain",
    )
    assert r.status_code == 201


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
    # sanitize_relpath rejects the ".." segment outright with 422; the
    # request never reaches the extension or MIME checks.
    assert r.status_code == 422


def test_upload_with_relative_path_stores_nested_file(
    client, job, db_session, uploads_dir
):
    _login_admin(client)
    files = {"file": ("foo.pdf", BytesIO(TINY_PDF), "application/pdf")}
    r = client.post(
        f"/api/jobs/{job.id}/attachments",
        files=files,
        data={"relative_path": "src/components/foo.pdf"},
    )
    assert r.status_code == 201
    assert r.json()["filename"] == "src/components/foo.pdf"

    on_disk = uploads_dir / "jobs" / str(job.id) / "src" / "components" / "foo.pdf"
    assert on_disk.exists()
    assert on_disk.read_bytes() == TINY_PDF


def test_upload_rejects_relative_path_with_parent_segment(client, job):
    _login_admin(client)
    files = {"file": ("foo.pdf", BytesIO(TINY_PDF), "application/pdf")}
    r = client.post(
        f"/api/jobs/{job.id}/attachments",
        files=files,
        data={"relative_path": "src/../../etc/foo.pdf"},
    )
    assert r.status_code == 422


def test_upload_rejects_junk_filename(client, job):
    _login_admin(client)
    files = {"file": (".DS_Store", BytesIO(b""), "application/octet-stream")}
    r = client.post(
        f"/api/jobs/{job.id}/attachments",
        files=files,
        data={"relative_path": "src/.DS_Store"},
    )
    assert r.status_code == 415
    assert "暫存" in r.json()["detail"]


def test_rename_in_folder_suffixes_last_segment(client, job, db_session, uploads_dir):
    _login_admin(client)
    base = {"file": ("foo.pdf", BytesIO(TINY_PDF), "application/pdf")}
    client.post(
        f"/api/jobs/{job.id}/attachments",
        files=base,
        data={"relative_path": "src/foo.pdf"},
    )
    r = client.post(
        f"/api/jobs/{job.id}/attachments",
        files=base,
        data={"relative_path": "src/foo.pdf", "conflict_strategy": "rename"},
    )
    assert r.status_code == 201
    assert r.json()["filename"] == "src/foo (1).pdf"

    assert (uploads_dir / "jobs" / str(job.id) / "src" / "foo (1).pdf").exists()


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


def test_upload_conflict_with_rename_appends_suffix(
    client, job, db_session, uploads_dir
):
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


def test_upload_conflict_with_overwrite_replaces_in_place(
    client, job, db_session, uploads_dir
):
    _login_admin(client)
    first = _upload(client, job.id, filename="report.pdf")
    original_id = first.json()["id"]
    original_path = uploads_dir / "jobs" / str(job.id) / "report.pdf"
    assert original_path.read_bytes() == TINY_PDF

    new_body = b"%PDF-1.7\n%new\n"
    r = _upload(
        client, job.id, filename="report.pdf", body=new_body, strategy="overwrite"
    )
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


def test_oversized_overwrite_leaves_the_existing_file_intact(
    client, job, db_session, uploads_dir
):
    """A failed replacement must not destroy what it was replacing.

    Uploads stream to disk now, and the overwrite path targets a file that
    already exists — so writing straight into it would truncate the stored
    attachment the instant the replacement ran over the cap. The bytes go to
    a sibling .part file and are moved into place only on success.
    """
    _login_admin(client)
    _upload(client, job.id, filename="report.pdf")
    stored = uploads_dir / "jobs" / str(job.id) / "report.pdf"
    assert stored.read_bytes() == TINY_PDF

    db_session.add(AppConfig(key="max_attachment_mb", value="0"))
    db_session.commit()

    r = _upload(
        client,
        job.id,
        filename="report.pdf",
        body=b"%PDF-1.7\nreplacement\n",
        strategy="overwrite",
    )
    assert r.status_code == 413
    assert stored.read_bytes() == TINY_PDF
    assert db_session.query(JobAttachment).filter_by(job_id=job.id).count() == 1


def test_rejected_upload_leaves_no_partial_file(client, job, db_session, uploads_dir):
    # The .part scratch file must be cleaned up, or the next upload of the
    # same name would find junk sitting next to it.
    db_session.add(AppConfig(key="max_attachment_mb", value="0"))
    db_session.commit()

    _login_admin(client)
    assert _upload(client, job.id, filename="report.pdf").status_code == 413

    job_dir = uploads_dir / "jobs" / str(job.id)
    leftovers = list(job_dir.iterdir()) if job_dir.exists() else []
    assert leftovers == [], leftovers
