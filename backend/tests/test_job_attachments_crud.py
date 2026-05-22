from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Job, JobAttachment, JobKind, User, UserRole
from app.routers.job_attachments import get_uploads_root

TINY_PDF = b"%PDF-1.4\n%\xc4\xe5\n"


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


def _upload(client, job_id, filename="report.pdf", body=TINY_PDF):
    files = {"file": (filename, BytesIO(body), "application/pdf")}
    return client.post(f"/api/jobs/{job_id}/attachments", files=files)


# ---------- LIST ----------


def test_list_attachments_requires_auth(client, job):
    r = client.get(f"/api/jobs/{job.id}/attachments")
    assert r.status_code == 401


def test_list_attachments_empty(client, job):
    _login_viewer(client)
    r = client.get(f"/api/jobs/{job.id}/attachments")
    assert r.status_code == 200
    assert r.json() == []


def test_list_attachments_returns_uploaded_rows_in_order(client, job):
    _login_admin(client)
    _upload(client, job.id, filename="a.pdf")
    _upload(client, job.id, filename="b.pdf")

    r = client.get(f"/api/jobs/{job.id}/attachments")
    assert r.status_code == 200
    names = [a["filename"] for a in r.json()]
    assert names == ["a.pdf", "b.pdf"]


def test_list_attachments_unknown_job_404(client):
    _login_viewer(client)
    r = client.get("/api/jobs/9999/attachments")
    assert r.status_code == 404


# ---------- DOWNLOAD ----------


def test_download_attachment_requires_auth(client, job):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]
    client.cookies.clear()

    r = client.get(f"/api/jobs/{job.id}/attachments/{attachment_id}")
    assert r.status_code == 401


def test_download_attachment_viewer_can_read(client, job):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]
    client.cookies.clear()

    _login_viewer(client)
    r = client.get(f"/api/jobs/{job.id}/attachments/{attachment_id}")
    assert r.status_code == 200
    assert r.content == TINY_PDF
    assert r.headers["content-type"].startswith("application/pdf")
    assert 'filename="report.pdf"' in r.headers["content-disposition"]


def test_download_handles_unicode_filename(client, job):
    _login_admin(client)
    up = _upload(client, job.id, filename="簡報.pdf")
    attachment_id = up.json()["id"]

    r = client.get(f"/api/jobs/{job.id}/attachments/{attachment_id}")
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    # RFC 5987 percent-encoded form sits alongside the legacy filename=.
    assert "filename*=UTF-8''" in cd
    assert "%E7%B0%A1%E5%A0%B1" in cd  # 簡報 percent-encoded


def test_download_404_when_attachment_unknown(client, job):
    _login_viewer(client)
    r = client.get(f"/api/jobs/{job.id}/attachments/9999")
    assert r.status_code == 404


def test_download_404_when_disk_file_missing(client, job, uploads_dir):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]

    # Simulate disk-side cleanup that the DB doesn't know about.
    (uploads_dir / "jobs" / str(job.id) / "report.pdf").unlink()

    r = client.get(f"/api/jobs/{job.id}/attachments/{attachment_id}")
    assert r.status_code == 404


def test_download_404_when_attachment_belongs_to_other_job(client, db_session):
    job_a = Job(
        job_year=2026,
        job_month=5,
        company="A",
        kind=JobKind.INTERNSHIP,
        experience_md="x",
    )
    job_b = Job(
        job_year=2026,
        job_month=5,
        company="B",
        kind=JobKind.INTERNSHIP,
        experience_md="y",
    )
    db_session.add_all([job_a, job_b])
    db_session.commit()

    _login_admin(client)
    up = _upload(client, job_a.id, filename="cv.pdf")
    attachment_id = up.json()["id"]

    # Same attachment ID under the wrong parent must not be readable.
    r = client.get(f"/api/jobs/{job_b.id}/attachments/{attachment_id}")
    assert r.status_code == 404


# ---------- DELETE ----------


def test_delete_attachment_requires_admin(client, job):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]
    client.cookies.clear()

    _login_viewer(client)
    r = client.delete(f"/api/jobs/{job.id}/attachments/{attachment_id}")
    assert r.status_code == 403


def test_delete_attachment_unauthenticated(client, job):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]
    client.cookies.clear()

    r = client.delete(f"/api/jobs/{job.id}/attachments/{attachment_id}")
    assert r.status_code == 401


def test_delete_removes_row_and_disk_file(client, job, db_session, uploads_dir):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]

    on_disk = uploads_dir / "jobs" / str(job.id) / "report.pdf"
    assert on_disk.exists()

    r = client.delete(f"/api/jobs/{job.id}/attachments/{attachment_id}")
    assert r.status_code == 204
    assert db_session.query(JobAttachment).filter_by(id=attachment_id).one_or_none() is None
    assert not on_disk.exists()


def test_delete_when_disk_file_already_gone_still_clears_row(client, job, db_session, uploads_dir):
    """If the disk file vanished out-of-band (manual cleanup, prior
    partial crash), the row deletion must still proceed so the
    attachment list reflects reality."""
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]

    (uploads_dir / "jobs" / str(job.id) / "report.pdf").unlink()

    r = client.delete(f"/api/jobs/{job.id}/attachments/{attachment_id}")
    assert r.status_code == 204
    assert db_session.query(JobAttachment).filter_by(id=attachment_id).one_or_none() is None


def test_delete_404_when_attachment_unknown(client, job):
    _login_admin(client)
    r = client.delete(f"/api/jobs/{job.id}/attachments/9999")
    assert r.status_code == 404


def test_delete_last_attachment_removes_job_directory(
    client, job, uploads_dir
):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]
    job_dir = uploads_dir / "jobs" / str(job.id)
    assert job_dir.exists()

    client.delete(f"/api/jobs/{job.id}/attachments/{attachment_id}")

    assert not job_dir.exists()


def test_delete_keeps_directory_when_other_attachments_remain(
    client, job, uploads_dir
):
    _login_admin(client)
    a = _upload(client, job.id, filename="a.pdf").json()["id"]
    _upload(client, job.id, filename="b.pdf")
    job_dir = uploads_dir / "jobs" / str(job.id)

    client.delete(f"/api/jobs/{job.id}/attachments/{a}")

    # b.pdf is still there so the directory must survive.
    assert job_dir.exists()
    assert (job_dir / "b.pdf").exists()


# ---------- PREVIEW (OnlyOffice-converted PDF) ----------


FAKE_PDF = b"%PDF-1.4\nFAKE PREVIEW\n"


def _upload_pptx(client, job_id, filename="deck.pptx"):
    files = {
        "file": (
            filename,
            BytesIO(b"PK\x03\x04 fake pptx"),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    }
    return client.post(f"/api/jobs/{job_id}/attachments", files=files)


def _stub_convert(monkeypatch, *, succeed: bool):
    """Replace office_convert.convert_to_pdf so the upload handler doesn't
    spawn OnlyOffice during the test. Returns the call count so tests
    can assert it was invoked exactly once."""
    from app.routers import job_attachments as router_mod

    calls = []

    def fake_convert(_job_id, source, output, *_a, **_kw):
        calls.append((source, output))
        if succeed:
            output.write_bytes(FAKE_PDF)
            return True
        return False

    monkeypatch.setattr(router_mod.office_convert, "convert_to_pdf", fake_convert)
    return calls


def test_upload_pptx_marks_preview_available_when_conversion_succeeds(
    client, job, monkeypatch
):
    _stub_convert(monkeypatch, succeed=True)
    _login_admin(client)

    r = _upload_pptx(client, job.id)
    assert r.status_code == 201
    assert r.json()["preview_available"] is True


def test_upload_pptx_marks_preview_unavailable_when_conversion_fails(
    client, job, monkeypatch
):
    _stub_convert(monkeypatch, succeed=False)
    _login_admin(client)

    r = _upload_pptx(client, job.id)
    assert r.status_code == 201
    assert r.json()["preview_available"] is False


def test_upload_non_office_does_not_call_converter(client, job, monkeypatch):
    calls = _stub_convert(monkeypatch, succeed=True)
    _login_admin(client)

    files = {"file": ("a.pdf", BytesIO(TINY_PDF), "application/pdf")}
    r = client.post(f"/api/jobs/{job.id}/attachments", files=files)
    assert r.status_code == 201
    assert r.json()["preview_available"] is False
    assert calls == []


def test_list_attachments_surfaces_preview_availability(
    client, job, monkeypatch, uploads_dir
):
    _stub_convert(monkeypatch, succeed=True)
    _login_admin(client)
    _upload_pptx(client, job.id, filename="deck.pptx")
    _upload(client, job.id, filename="report.pdf")

    r = client.get(f"/api/jobs/{job.id}/attachments")
    rows = {row["filename"]: row for row in r.json()}
    assert rows["deck.pptx"]["preview_available"] is True
    assert rows["report.pdf"]["preview_available"] is False


def test_preview_endpoint_returns_pdf_when_available(
    client, job, monkeypatch, uploads_dir
):
    _stub_convert(monkeypatch, succeed=True)
    _login_admin(client)
    up = _upload_pptx(client, job.id)
    attachment_id = up.json()["id"]
    client.cookies.clear()

    _login_viewer(client)
    r = client.get(f"/api/jobs/{job.id}/attachments/{attachment_id}/preview")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content == FAKE_PDF


def test_preview_endpoint_404_when_no_preview_was_generated(
    client, job, monkeypatch
):
    _stub_convert(monkeypatch, succeed=False)
    _login_admin(client)
    up = _upload_pptx(client, job.id)
    attachment_id = up.json()["id"]

    r = client.get(f"/api/jobs/{job.id}/attachments/{attachment_id}/preview")
    assert r.status_code == 404


def test_preview_endpoint_requires_auth(client, job, monkeypatch):
    _stub_convert(monkeypatch, succeed=True)
    _login_admin(client)
    up = _upload_pptx(client, job.id)
    attachment_id = up.json()["id"]
    client.cookies.clear()

    r = client.get(f"/api/jobs/{job.id}/attachments/{attachment_id}/preview")
    assert r.status_code == 401


def test_overwrite_regenerates_preview(
    client, job, monkeypatch, uploads_dir
):
    succeed = True
    pdfs = [b"%PDF-1.4\nFIRST", b"%PDF-1.4\nSECOND"]
    from app.routers import job_attachments as router_mod

    invocations = {"n": 0}

    def fake_convert(_job_id, source, output, *_a, **_kw):
        if not succeed:
            return False
        output.write_bytes(pdfs[invocations["n"]])
        invocations["n"] += 1
        return True

    monkeypatch.setattr(router_mod.office_convert, "convert_to_pdf", fake_convert)

    _login_admin(client)
    up = _upload_pptx(client, job.id, filename="deck.pptx")
    attachment_id = up.json()["id"]

    # Confirm the first preview is what we expect.
    assert (
        client.get(
            f"/api/jobs/{job.id}/attachments/{attachment_id}/preview"
        ).content
        == pdfs[0]
    )

    # Overwrite the .pptx and expect a fresh preview body.
    files = {
        "file": (
            "deck.pptx",
            BytesIO(b"PK\x03\x04 second"),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    }
    r = client.post(
        f"/api/jobs/{job.id}/attachments",
        files=files,
        data={"conflict_strategy": "overwrite"},
    )
    assert r.status_code == 201

    assert (
        client.get(
            f"/api/jobs/{job.id}/attachments/{attachment_id}/preview"
        ).content
        == pdfs[1]
    )


def test_delete_also_removes_preview_pdf(
    client, job, monkeypatch, uploads_dir
):
    _stub_convert(monkeypatch, succeed=True)
    _login_admin(client)
    up = _upload_pptx(client, job.id, filename="deck.pptx")
    attachment_id = up.json()["id"]
    preview_path = uploads_dir / "jobs" / str(job.id) / "deck.pptx.preview.pdf"
    assert preview_path.exists()

    r = client.delete(f"/api/jobs/{job.id}/attachments/{attachment_id}")
    assert r.status_code == 204
    assert not preview_path.exists()
