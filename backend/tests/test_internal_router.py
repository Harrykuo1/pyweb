"""Tests for the /internal source endpoint that OnlyOffice fetches from."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.routers.job_attachments import get_uploads_root


@pytest.fixture
def uploads_dir(tmp_path) -> Path:
    return tmp_path / "uploads"


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


def _seed_file(uploads_dir, job_id, filename, body=b"hello"):
    job_dir = uploads_dir / "jobs" / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / filename).write_bytes(body)


def test_serve_source_returns_file_on_disk(client, uploads_dir):
    _seed_file(uploads_dir, 7, "deck.pptx", b"PK\x03\x04 fake")

    r = client.get("/internal/source/7/deck.pptx")
    assert r.status_code == 200
    assert r.content == b"PK\x03\x04 fake"


def test_serve_source_idempotent_across_reads(client, uploads_dir):
    """OnlyOffice retries the source fetch on transient errors during a
    conversion, so the endpoint has to keep resolving for the full
    conversion window — no single-use semantics."""
    _seed_file(uploads_dir, 7, "deck.pptx", b"abc")

    assert client.get("/internal/source/7/deck.pptx").status_code == 200
    assert client.get("/internal/source/7/deck.pptx").status_code == 200


def test_serve_source_404_when_file_missing(client, uploads_dir):
    # Job directory doesn't exist at all.
    r = client.get("/internal/source/7/missing.pptx")
    assert r.status_code == 404


def test_serve_source_rejects_path_traversal(client, uploads_dir):
    _seed_file(uploads_dir, 7, "deck.pptx", b"abc")

    # Encoded ".." segments survive URL parsing but the basename check
    # collapses them to "..", which the endpoint treats as a 404.
    r = client.get("/internal/source/7/..%2Fsecret.txt")
    assert r.status_code == 404


def test_serve_source_does_not_require_session(client, uploads_dir):
    """No login cookie is sent and yet the file comes back — this is the
    contract OnlyOffice depends on. The backend port is expose-only
    on the compose network, so non-internal callers can't reach this
    endpoint anyway."""
    _seed_file(uploads_dir, 7, "deck.pptx", b"x")
    client.cookies.clear()

    r = client.get("/internal/source/7/deck.pptx")
    assert r.status_code == 200


def test_serve_source_resolves_multi_segment_relpath(client, uploads_dir):
    """Folder uploads land at e.g. src/components/Foo.vue; OnlyOffice
    fetches via the same path. ``{filename:path}`` lets multi-segment
    relpaths through."""
    job_dir = uploads_dir / "jobs" / "7" / "src" / "components"
    job_dir.mkdir(parents=True)
    (job_dir / "Foo.docx").write_bytes(b"nested")

    r = client.get("/internal/source/7/src/components/Foo.docx")
    assert r.status_code == 200
    assert r.content == b"nested"


