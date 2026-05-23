"""Lock-in tests for the photo / resume_pdf BLOB deferral optimisation.

The list endpoint historically loaded every member row in full,
including the multi-MB photo and resume PDF columns, only to discard
them during response serialization. We marked those two columns
deferred=True on the model and rewrote has_photo / has_resume_pdf to
read companion non-deferred columns (photo_content_type and
resume_pdf_updated_at) instead of the BLOBs themselves.

These tests guard against two regressions:
  1. Someone removing deferred=True (so list queries pull BLOBs again).
  2. Someone reverting has_photo / has_resume_pdf to read the BLOB
     column, which would trigger a per-row SELECT during response
     serialization — turning the optimisation into a real N+1.

Photo storage has since moved to the filesystem (photo_path), so the
GET endpoint never touches the BLOB column either — the deferral
optimisation is now strictly a safety net while the column itself is
on its way out. The seeding here mirrors a post-FS-rollout row:
photo_path set, photo BLOB NULL. Resume PDFs still live in the BLOB
column until their own router migration lands.
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole
from app.routers.members import get_uploads_root
from tests.conftest import count_queries


TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000000500010d0a2db40000000049454e44"
    "ae426082"
)
TINY_PDF = b"%PDF-1.4\n%fake\n%%EOF\n"


@pytest.fixture
def uploads_dir(tmp_path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def populated(db_session, uploads_dir):
    """Seed admin + 5 members each with a photo (FS-backed) and a
    resume_pdf BLOB so the 'real' list query has multiple rows to
    potentially N+1 over."""
    db_session.add(
        User(username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN)
    )
    for i in range(5):
        member_id = i + 1
        relpath = f"members/{member_id}/photo.png"
        on_disk = uploads_dir / relpath
        on_disk.parent.mkdir(parents=True, exist_ok=True)
        on_disk.write_bytes(TINY_PNG)
        db_session.add(
            Member(
                id=member_id,
                graduation_year=2020 + i,
                real_name=f"Member {i}",
                institution="SWE",
                photo_path=relpath,
                photo_content_type="image/png",
                photo_updated_at=datetime.now(timezone.utc),
                resume_pdf=TINY_PDF,
                resume_pdf_updated_at=datetime.now(timezone.utc),
                joined_at=datetime.now(timezone.utc),
            )
        )
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_uploads_root] = lambda: uploads_dir
    client = TestClient(app)
    client.post("/api/auth/login", json={"password": "admin-pw"})

    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


def _list_member_select(statements: list[str]) -> str | None:
    """Return the SELECT issued by GET /api/members, or None."""
    for stmt in statements:
        normalised = stmt.lower().replace("\n", " ")
        if "from members" in normalised and normalised.strip().startswith("select"):
            return stmt
    return None


def test_list_members_does_not_select_blob_columns(populated, db_engine):
    with count_queries(db_engine) as statements:
        r = populated.get("/api/members")
        assert r.status_code == 200
        assert len(r.json()) == 5

    list_select = _list_member_select(statements)
    assert list_select is not None, f"no SELECT against members observed; got {statements}"

    # The two deferred BLOB columns must not appear in the column list.
    # Comparing on substring is enough: SQLAlchemy emits column names
    # bare in the SELECT projection.
    assert "members.photo," not in list_select.lower() and \
           "members.photo " not in list_select.lower(), \
           f"photo BLOB leaked into list query: {list_select}"
    assert "members.resume_pdf," not in list_select.lower() and \
           "members.resume_pdf " not in list_select.lower(), \
           f"resume_pdf BLOB leaked into list query: {list_select}"


def test_list_members_issues_no_per_row_blob_load(populated, db_engine):
    # If has_photo / has_resume_pdf accidentally read the deferred
    # column during MemberResponse serialization, we'd see one extra
    # SELECT per member (5 rows -> 5 deferred loads). The list query
    # itself plus auth lookups are a small constant; cap well below
    # what an N+1 would produce.
    with count_queries(db_engine) as statements:
        r = populated.get("/api/members")
        assert r.status_code == 200

    blob_loads = [
        s for s in statements
        if "from members" in s.lower()
        and ("members.photo" in s.lower() or "members.resume_pdf" in s.lower())
        and "where members.id" in s.lower()
    ]
    assert blob_loads == [], (
        f"deferred BLOB columns were per-row loaded ({len(blob_loads)} times) "
        f"during list serialization — likely a regression in has_photo / "
        f"has_resume_pdf reading the deferred column directly. "
        f"Sample: {blob_loads[:1]}"
    )


def test_get_photo_endpoint_serves_from_disk_without_loading_blob(
    populated, db_engine
):
    # Photo storage moved to the filesystem, so even the single-row
    # endpoint must not touch the BLOB column. If a future change
    # accidentally reintroduces a `member.photo` read, the deferred
    # load shows up here as an extra SELECT against the BLOB column.
    with count_queries(db_engine) as statements:
        r = populated.get("/api/members/1/photo")
        assert r.status_code == 200
        assert r.content == TINY_PNG

    blob_loads = [
        s for s in statements
        if "members.photo " in s.lower() or "members.photo," in s.lower()
    ]
    assert blob_loads == [], (
        f"GET /api/members/{{id}}/photo loaded the deferred BLOB column — "
        f"the endpoint should be reading photo_path and streaming from "
        f"disk only. Statements: {blob_loads}"
    )


def test_has_photo_property_does_not_trigger_blob_load(populated, db_session, db_engine):
    # Direct ORM access path: load a member without touching photo,
    # then ask has_photo. Should not cause a SELECT on the photo column.
    member = db_session.query(Member).filter_by(id=1).one()

    # Expire so SQLAlchemy will go back to the DB if it's asked.
    db_session.expire(member, ["photo", "resume_pdf"])

    with count_queries(db_engine) as statements:
        assert member.has_photo is True
        assert member.has_resume_pdf is True

    blob_loads = [
        s for s in statements
        if "members.photo" in s.lower() or "members.resume_pdf" in s.lower()
    ]
    assert blob_loads == [], (
        f"has_photo / has_resume_pdf triggered a BLOB load — they should "
        f"be reading the small companion columns instead. Statements: {blob_loads}"
    )


def test_has_photo_property_correct_with_and_without_photo(populated, db_session):
    # Sanity: the rewritten property still returns the right answer.
    with_photo = db_session.query(Member).filter_by(id=1).one()
    assert with_photo.has_photo is True
    assert with_photo.has_resume_pdf is True

    # Mutate one row to clear photo + companion column, mirroring what
    # the delete endpoint does.
    with_photo.photo_path = None
    with_photo.photo_content_type = None
    with_photo.photo_updated_at = None
    with_photo.resume_pdf = None
    with_photo.resume_pdf_updated_at = None
    db_session.commit()
    db_session.refresh(with_photo)

    assert with_photo.has_photo is False
    assert with_photo.has_resume_pdf is False
