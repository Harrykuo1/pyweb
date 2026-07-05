import zipfile
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


def _upload(client, job_id, filename="report.pdf", body=TINY_PDF):
    files = {"file": (filename, BytesIO(body), "application/pdf")}
    return client.post(f"/api/jobs/{job_id}/attachments", files=files)


ADMIN_PW = "admin-pw"


def _delete_attachment(client, job_id, attachment_id, password=ADMIN_PW):
    """DELETE with a JSON body — httpx's TestClient.delete() doesn't take a
    json= kwarg, so go through .request() like the members tests do."""
    return client.request(
        "DELETE",
        f"/api/jobs/{job_id}/attachments/{attachment_id}",
        json={"password": password},
    )


def _bulk_delete(client, job_id, ids, password=ADMIN_PW):
    return client.post(
        f"/api/jobs/{job_id}/attachments/bulk-delete",
        json={"ids": ids, "password": password},
    )


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
    # PDFs are in the preview-inline allowlist so they get
    # Content-Disposition: inline (the viewer's <embed src=> needs it).
    cd = r.headers["content-disposition"]
    assert cd.startswith("inline;")
    assert 'filename="report.pdf"' in cd
    # nosniff is always-on as defence-in-depth.
    assert r.headers.get("x-content-type-options") == "nosniff"


def test_download_forces_attachment_for_non_preview_safe_types(client, job):
    """HTML / SVG / source code etc. ride the same download URL but
    must not get inline rendering — that's how a hostile upload would
    turn into an XSS surface. The attachment disposition + nosniff
    keeps browsers from interpreting the bytes."""
    _login_admin(client)
    files = {
        "file": (
            "snippet.html",
            BytesIO(b"<script>alert(1)</script>"),
            "text/html",
        ),
    }
    up = client.post(f"/api/jobs/{job.id}/attachments", files=files)
    attachment_id = up.json()["id"]

    r = client.get(f"/api/jobs/{job.id}/attachments/{attachment_id}")
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    assert cd.startswith("attachment;")
    assert r.headers.get("x-content-type-options") == "nosniff"


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
    # Viewer's session can't reach the handler — auth dependency runs
    # before the body password is checked, so the viewer-pw is moot.
    r = _delete_attachment(client, job.id, attachment_id, password="viewer-pw")
    assert r.status_code == 403


def test_delete_attachment_unauthenticated(client, job):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]
    client.cookies.clear()

    r = _delete_attachment(client, job.id, attachment_id)
    assert r.status_code == 401


def test_delete_attachment_wrong_password_422(client, job):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]

    r = _delete_attachment(client, job.id, attachment_id, password="wrong")
    assert r.status_code == 422
    # And the row + file are still there — the wrong-password path
    # must not delete anything on its way out.
    assert (
        client.get(f"/api/jobs/{job.id}/attachments/{attachment_id}").status_code == 200
    )


def test_delete_attachment_missing_password_422(client, job):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]

    r = client.request(
        "DELETE",
        f"/api/jobs/{job.id}/attachments/{attachment_id}",
    )
    assert r.status_code == 422


def test_delete_removes_row_and_disk_file(client, job, db_session, uploads_dir):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]

    on_disk = uploads_dir / "jobs" / str(job.id) / "report.pdf"
    assert on_disk.exists()

    r = _delete_attachment(client, job.id, attachment_id)
    assert r.status_code == 204
    assert (
        db_session.query(JobAttachment).filter_by(id=attachment_id).one_or_none()
        is None
    )
    assert not on_disk.exists()


def test_delete_when_disk_file_already_gone_still_clears_row(
    client, job, db_session, uploads_dir
):
    """If the disk file vanished out-of-band (manual cleanup, prior
    partial crash), the row deletion must still proceed so the
    attachment list reflects reality."""
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]

    (uploads_dir / "jobs" / str(job.id) / "report.pdf").unlink()

    r = _delete_attachment(client, job.id, attachment_id)
    assert r.status_code == 204
    assert (
        db_session.query(JobAttachment).filter_by(id=attachment_id).one_or_none()
        is None
    )


def test_delete_404_when_attachment_unknown(client, job):
    _login_admin(client)
    r = _delete_attachment(client, job.id, 9999)
    assert r.status_code == 404


def test_delete_last_attachment_removes_job_directory(client, job, uploads_dir):
    _login_admin(client)
    up = _upload(client, job.id, filename="report.pdf")
    attachment_id = up.json()["id"]
    job_dir = uploads_dir / "jobs" / str(job.id)
    assert job_dir.exists()

    _delete_attachment(client, job.id, attachment_id)

    assert not job_dir.exists()


def test_delete_keeps_directory_when_other_attachments_remain(client, job, uploads_dir):
    _login_admin(client)
    a = _upload(client, job.id, filename="a.pdf").json()["id"]
    _upload(client, job.id, filename="b.pdf")
    job_dir = uploads_dir / "jobs" / str(job.id)

    _delete_attachment(client, job.id, a)

    # b.pdf is still there so the directory must survive.
    assert job_dir.exists()
    assert (job_dir / "b.pdf").exists()


def test_delete_cleans_empty_intermediate_dirs_in_folder_upload(
    client, job, uploads_dir
):
    """Folder uploads land at e.g. src/components/foo.pdf. When the
    last file under src/components/ is deleted, the empty src/ and
    src/components/ directories should be reaped — but only as long
    as no other sibling files still need them."""
    _login_admin(client)
    files = {"file": ("foo.pdf", BytesIO(TINY_PDF), "application/pdf")}
    up = client.post(
        f"/api/jobs/{job.id}/attachments",
        files=files,
        data={"relative_path": "src/components/foo.pdf"},
    )
    attachment_id = up.json()["id"]
    job_dir = uploads_dir / "jobs" / str(job.id)
    assert (job_dir / "src" / "components" / "foo.pdf").exists()

    _delete_attachment(client, job.id, attachment_id)

    # Walks up from src/components/ through src/ and into the per-job
    # directory; with no other files left, everything goes.
    assert not (job_dir / "src" / "components").exists()
    assert not (job_dir / "src").exists()
    assert not job_dir.exists()


def test_delete_keeps_intermediate_dir_with_sibling_file(client, job, uploads_dir):
    _login_admin(client)
    files = {"file": ("a.pdf", BytesIO(TINY_PDF), "application/pdf")}
    a = client.post(
        f"/api/jobs/{job.id}/attachments",
        files=files,
        data={"relative_path": "src/a.pdf"},
    ).json()["id"]
    client.post(
        f"/api/jobs/{job.id}/attachments",
        files={"file": ("b.pdf", BytesIO(TINY_PDF), "application/pdf")},
        data={"relative_path": "src/b.pdf"},
    )

    _delete_attachment(client, job.id, a)

    job_dir = uploads_dir / "jobs" / str(job.id)
    assert (job_dir / "src" / "b.pdf").exists()
    assert (job_dir / "src").exists()  # not empty, must stay


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

    def fake_convert(_job_id, source, _relpath, output, *_a, **_kw):
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


def test_preview_endpoint_404_when_no_preview_was_generated(client, job, monkeypatch):
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


def test_overwrite_regenerates_preview(client, job, monkeypatch, uploads_dir):
    succeed = True
    pdfs = [b"%PDF-1.4\nFIRST", b"%PDF-1.4\nSECOND"]
    from app.routers import job_attachments as router_mod

    invocations = {"n": 0}

    def fake_convert(_job_id, source, _relpath, output, *_a, **_kw):
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
        client.get(f"/api/jobs/{job.id}/attachments/{attachment_id}/preview").content
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
        client.get(f"/api/jobs/{job.id}/attachments/{attachment_id}/preview").content
        == pdfs[1]
    )


def test_delete_also_removes_preview_pdf(client, job, monkeypatch, uploads_dir):
    _stub_convert(monkeypatch, succeed=True)
    _login_admin(client)
    up = _upload_pptx(client, job.id, filename="deck.pptx")
    attachment_id = up.json()["id"]
    preview_path = uploads_dir / "jobs" / str(job.id) / "deck.pptx.preview.pdf"
    assert preview_path.exists()

    r = _delete_attachment(client, job.id, attachment_id)
    assert r.status_code == 204
    assert not preview_path.exists()


# ---------- BULK DELETE ----------


def test_bulk_delete_requires_admin(client, job):
    _login_admin(client)
    a = _upload(client, job.id, filename="a.pdf").json()["id"]
    client.cookies.clear()

    _login_viewer(client)
    r = _bulk_delete(client, job.id, [a], password="viewer-pw")
    assert r.status_code == 403


def test_bulk_delete_unauthenticated(client, job):
    _login_admin(client)
    a = _upload(client, job.id, filename="a.pdf").json()["id"]
    client.cookies.clear()

    r = _bulk_delete(client, job.id, [a])
    assert r.status_code == 401


def test_bulk_delete_wrong_password_422(client, job):
    _login_admin(client)
    a = _upload(client, job.id, filename="a.pdf").json()["id"]

    r = _bulk_delete(client, job.id, [a], password="wrong")
    assert r.status_code == 422
    # Row must still be present — no silent partial deletion when the
    # password doesn't match.
    assert client.get(f"/api/jobs/{job.id}/attachments/{a}").status_code == 200


def test_bulk_delete_rejects_empty_ids(client, job):
    _login_admin(client)
    r = _bulk_delete(client, job.id, [])
    assert r.status_code == 422


def test_bulk_delete_rejects_too_many_ids(client, job):
    _login_admin(client)
    r = _bulk_delete(client, job.id, list(range(1, 502)))
    assert r.status_code == 422


def test_bulk_delete_removes_multiple_rows_and_files(
    client, job, db_session, uploads_dir
):
    _login_admin(client)
    a = _upload(client, job.id, filename="a.pdf").json()["id"]
    b = _upload(client, job.id, filename="b.pdf").json()["id"]
    c = _upload(client, job.id, filename="c.pdf").json()["id"]

    r = _bulk_delete(client, job.id, [a, b])
    assert r.status_code == 200
    assert r.json() == {"deleted": 2}

    remaining = {
        row.id for row in db_session.query(JobAttachment).filter_by(job_id=job.id)
    }
    assert remaining == {c}

    job_dir = uploads_dir / "jobs" / str(job.id)
    assert not (job_dir / "a.pdf").exists()
    assert not (job_dir / "b.pdf").exists()
    assert (job_dir / "c.pdf").exists()


def test_bulk_delete_also_removes_preview_pdfs(client, job, monkeypatch, uploads_dir):
    _stub_convert(monkeypatch, succeed=True)
    _login_admin(client)
    deck = _upload_pptx(client, job.id, filename="deck.pptx").json()["id"]
    preview = uploads_dir / "jobs" / str(job.id) / "deck.pptx.preview.pdf"
    assert preview.exists()

    r = _bulk_delete(client, job.id, [deck])
    assert r.status_code == 200
    assert not preview.exists()


def test_bulk_delete_clears_empty_intermediate_dirs(client, job, uploads_dir):
    """Bulk delete spanning multiple folder branches must collapse
    every newly-empty descendant, not just the parents of the last
    file processed."""
    _login_admin(client)
    a = client.post(
        f"/api/jobs/{job.id}/attachments",
        files={"file": ("a.pdf", BytesIO(TINY_PDF), "application/pdf")},
        data={"relative_path": "src/a.pdf"},
    ).json()["id"]
    b = client.post(
        f"/api/jobs/{job.id}/attachments",
        files={"file": ("b.pdf", BytesIO(TINY_PDF), "application/pdf")},
        data={"relative_path": "docs/team/b.pdf"},
    ).json()["id"]

    r = _bulk_delete(client, job.id, [a, b])
    assert r.status_code == 200

    job_dir = uploads_dir / "jobs" / str(job.id)
    assert not (job_dir / "src").exists()
    assert not (job_dir / "docs" / "team").exists()
    assert not (job_dir / "docs").exists()
    # Job had no other files — reap the per-job dir too.
    assert not job_dir.exists()


def test_bulk_delete_keeps_dirs_with_surviving_siblings(client, job, uploads_dir):
    _login_admin(client)
    a = client.post(
        f"/api/jobs/{job.id}/attachments",
        files={"file": ("a.pdf", BytesIO(TINY_PDF), "application/pdf")},
        data={"relative_path": "src/a.pdf"},
    ).json()["id"]
    client.post(
        f"/api/jobs/{job.id}/attachments",
        files={"file": ("b.pdf", BytesIO(TINY_PDF), "application/pdf")},
        data={"relative_path": "src/b.pdf"},
    )

    r = _bulk_delete(client, job.id, [a])
    assert r.status_code == 200

    job_dir = uploads_dir / "jobs" / str(job.id)
    assert (job_dir / "src" / "b.pdf").exists()
    assert (job_dir / "src").exists()


def test_bulk_delete_silently_skips_ids_from_other_jobs(client, db_session):
    """Cross-job IDs in the payload must not affect the other job.
    The endpoint scopes its query by job_id; foreign IDs filter out at
    the SQL layer rather than 404-ing, so a partial selection on the
    UI side still cleans up what's legitimately the user's."""
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
    a_in_a = _upload(client, job_a.id, filename="a.pdf").json()["id"]
    b_in_b = _upload(client, job_b.id, filename="b.pdf").json()["id"]

    # Spray a delete at job_a but include b_in_b — the cross-job ID
    # should be ignored, not honored.
    r = _bulk_delete(client, job_a.id, [a_in_a, b_in_b])
    assert r.status_code == 200
    assert r.json() == {"deleted": 1}

    # job_b's row is untouched.
    assert (
        db_session.query(JobAttachment).filter_by(id=b_in_b).one_or_none() is not None
    )


def test_bulk_delete_unknown_ids_count_as_zero(client, job):
    _login_admin(client)
    r = _bulk_delete(client, job.id, [9999, 8888])
    assert r.status_code == 200
    assert r.json() == {"deleted": 0}


# ---------- BULK DOWNLOAD ----------


def _bulk_download_url(job_id):
    return f"/api/jobs/{job_id}/attachments/bulk-download"


def test_bulk_download_requires_auth(client, job):
    _login_admin(client)
    a = _upload(client, job.id, filename="a.pdf").json()["id"]
    client.cookies.clear()

    r = client.post(_bulk_download_url(job.id), json={"ids": [a]})
    assert r.status_code == 401


def test_bulk_download_viewer_can_download(client, job):
    """Bulk download is read-only — same auth gate as listing or
    downloading single files. A viewer who can pull files one at a
    time can pull them all in a zip; no privilege escalation."""
    _login_admin(client)
    a = _upload(client, job.id, filename="a.pdf").json()["id"]
    b = _upload(client, job.id, filename="b.pdf").json()["id"]
    client.cookies.clear()

    _login_viewer(client)
    r = client.post(_bulk_download_url(job.id), json={"ids": [a, b]})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"


def test_bulk_download_returns_zip_with_selected_files(client, job):
    _login_admin(client)
    a = _upload(client, job.id, filename="a.pdf", body=b"%PDF-1.4\nAAA").json()["id"]
    b = _upload(client, job.id, filename="b.pdf", body=b"%PDF-1.4\nBBB").json()["id"]
    _upload(client, job.id, filename="c.pdf", body=b"%PDF-1.4\nCCC")

    r = client.post(_bulk_download_url(job.id), json={"ids": [a, b]})
    assert r.status_code == 200

    with zipfile.ZipFile(BytesIO(r.content)) as zf:
        names = sorted(zf.namelist())
        assert names == ["a.pdf", "b.pdf"]
        assert zf.read("a.pdf") == b"%PDF-1.4\nAAA"
        assert zf.read("b.pdf") == b"%PDF-1.4\nBBB"


def test_bulk_download_preserves_folder_relpaths_inside_zip(client, job):
    _login_admin(client)
    a = client.post(
        f"/api/jobs/{job.id}/attachments",
        files={"file": ("foo.pdf", BytesIO(TINY_PDF), "application/pdf")},
        data={"relative_path": "src/components/foo.pdf"},
    ).json()["id"]

    r = client.post(_bulk_download_url(job.id), json={"ids": [a]})
    assert r.status_code == 200
    with zipfile.ZipFile(BytesIO(r.content)) as zf:
        assert zf.namelist() == ["src/components/foo.pdf"]


def test_bulk_download_skips_disk_missing_rows(client, job, uploads_dir):
    """A DB row whose on-disk file vanished out-of-band should be
    silently skipped — the rest of the zip still produces. Mirrors
    the download endpoint's tolerance of orphans."""
    _login_admin(client)
    a = _upload(client, job.id, filename="a.pdf", body=b"AA").json()["id"]
    b = _upload(client, job.id, filename="b.pdf", body=b"BB").json()["id"]
    (uploads_dir / "jobs" / str(job.id) / "a.pdf").unlink()

    r = client.post(_bulk_download_url(job.id), json={"ids": [a, b]})
    assert r.status_code == 200
    with zipfile.ZipFile(BytesIO(r.content)) as zf:
        assert zf.namelist() == ["b.pdf"]


def test_bulk_download_filters_cross_job_ids(client, db_session):
    """Foreign IDs in the payload silently filter out at the SQL
    level so a partial selection on the UI side can't leak files from
    another job into the zip."""
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
    _ = _upload(client, job_a.id, filename="a.pdf", body=b"AA").json()["id"]
    b_in_b = _upload(client, job_b.id, filename="b.pdf", body=b"BB").json()["id"]

    r = client.post(_bulk_download_url(job_a.id), json={"ids": [b_in_b]})
    assert r.status_code == 200
    with zipfile.ZipFile(BytesIO(r.content)) as zf:
        # b_in_b belongs to job_b, asking under job_a's URL must yield
        # an empty zip rather than expose it.
        assert zf.namelist() == []


def test_bulk_download_rejects_empty_ids(client, job):
    _login_admin(client)
    r = client.post(_bulk_download_url(job.id), json={"ids": []})
    assert r.status_code == 422


def test_bulk_download_unknown_job_404(client):
    _login_admin(client)
    r = client.post(_bulk_download_url(9999), json={"ids": [1]})
    assert r.status_code == 404
