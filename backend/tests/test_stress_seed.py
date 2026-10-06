"""Tests for the standalone stress-test seed script.

The script writes its own engine bound to whatever --db-url it is given,
so we point it at a disposable PostgreSQL schema. We pass deterministic
seed_value so probabilistic assertions (about how many rows happen to
have timeline events) are reproducible without flaking the suite.

Pillow + reportlab come from requirements-dev.txt; if they are missing
the photo / PDF generators raise ImportError, which is fine — these
tests run in the same dev venv that installs the dev requirements.

Each generated member triggers a JPEG render + PDF render, so test N
is kept at 3 — assertions only need a handful to be meaningful and
the photos / PDFs are not cheap to produce.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from scripts import stress_seed


def _connect(db_url):
    return create_engine(db_url, future=True).connect()


@pytest.fixture
def uploads_dir(tmp_path) -> Path:
    return tmp_path / "uploads"


def test_seed_inserts_requested_counts(postgres_url, uploads_dir):
    db_url = postgres_url
    summary = stress_seed.seed(
        db_url=db_url,
        uploads_dir=uploads_dir,
        members=3,
        jobs=3,
        batch=3,
        needle_every=0,
        seed_value=42,
    )

    assert summary["members_total"] == 3
    assert summary["jobs_total"] == 3

    with _connect(db_url) as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM members")).scalar() == 3
        assert conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar() == 3
        # The script supplies member IDs for upload paths. Subsequent ordinary
        # inserts must continue after them rather than collide with ID 1.
        assert (
            conn.execute(
                text("SELECT nextval(pg_get_serial_sequence('members', 'id'))")
            ).scalar_one()
            == 4
        )


def test_seed_reset_clears_tables_before_inserting(postgres_url, uploads_dir):
    db_url = postgres_url
    stress_seed.seed(
        db_url=db_url,
        uploads_dir=uploads_dir,
        members=3,
        jobs=3,
        batch=3,
        needle_every=0,
        seed_value=1,
    )
    # Re-run with reset=True; expect the second invocation's count, not 6.
    stress_seed.seed(
        db_url=db_url,
        uploads_dir=uploads_dir,
        members=1,
        jobs=1,
        batch=1,
        needle_every=0,
        reset=True,
        seed_value=2,
    )

    with _connect(db_url) as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM members")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar() == 1


def test_seed_injects_needles_at_expected_cadence(postgres_url, uploads_dir):
    db_url = postgres_url
    # needle_every=2 with N=3 → idx 0 and 2 get needles → 2 each.
    stress_seed.seed(
        db_url=db_url,
        uploads_dir=uploads_dir,
        members=3,
        jobs=3,
        batch=3,
        needle_every=2,
        seed_value=42,
    )

    with _connect(db_url) as conn:
        member_needles = conn.execute(
            text(
                "SELECT COUNT(*) FROM members WHERE resume_md LIKE '%STRESS_NEEDLE_M%'"
            )
        ).scalar()
        job_needles = conn.execute(
            text(
                "SELECT COUNT(*) FROM jobs WHERE experience_md LIKE '%STRESS_NEEDLE_J%'"
            )
        ).scalar()
        assert member_needles == 2
        assert job_needles == 2


def test_seed_writes_real_jpeg_photos(postgres_url, uploads_dir):
    db_url = postgres_url
    stress_seed.seed(
        db_url=db_url,
        uploads_dir=uploads_dir,
        members=3,
        jobs=0,
        batch=3,
        needle_every=0,
        seed_value=42,
    )

    with _connect(db_url) as conn:
        paths = [
            r[0]
            for r in conn.execute(
                text("SELECT photo_path FROM members WHERE photo_path IS NOT NULL")
            ).all()
        ]
    assert len(paths) == 3
    for rel in paths:
        blob = (uploads_dir / rel).read_bytes()
        assert blob[:3] == b"\xff\xd8\xff", f"{rel} is not a valid JPEG"
        # The gradient + confetti + avatar circle compresses to
        # roughly 10-30 KB; sanity-check we're in the right ballpark.
        assert 5_000 < len(blob) < 200_000


def test_seed_writes_real_pdf_resumes(postgres_url, uploads_dir):
    db_url = postgres_url
    stress_seed.seed(
        db_url=db_url,
        uploads_dir=uploads_dir,
        members=3,
        jobs=0,
        batch=3,
        needle_every=0,
        seed_value=42,
    )

    with _connect(db_url) as conn:
        paths = [
            r[0]
            for r in conn.execute(
                text(
                    "SELECT resume_pdf_path FROM members "
                    "WHERE resume_pdf_path IS NOT NULL"
                )
            ).all()
        ]
    assert len(paths) == 3
    for rel in paths:
        blob = (uploads_dir / rel).read_bytes()
        assert blob[:5] == b"%PDF-", f"{rel} is not a valid PDF"
        assert b"%%EOF" in blob[-32:]
        assert 5_000 < len(blob) < 200_000


def test_seed_populates_required_member_fields(postgres_url, uploads_dir):
    db_url = postgres_url
    stress_seed.seed(
        db_url=db_url,
        uploads_dir=uploads_dir,
        members=3,
        jobs=0,
        batch=3,
        needle_every=0,
        seed_value=42,
    )

    with _connect(db_url) as conn:
        # Required (non-null) columns must always be set, plus the path
        # columns which are now mandatory for every seeded member.
        nulls = conn.execute(
            text(
                "SELECT COUNT(*) FROM members "
                "WHERE real_name IS NULL OR real_name = '' "
                "   OR institution IS NULL OR institution = '' "
                "   OR graduation_year IS NULL "
                "   OR joined_at IS NULL "
                "   OR resume_md IS NULL OR resume_md = '' "
                "   OR photo_path IS NULL "
                "   OR resume_pdf_path IS NULL"
            )
        ).scalar()
        assert nulls == 0


def test_seed_writes_structured_timeline_events(postgres_url, uploads_dir):
    db_url = postgres_url
    stress_seed.seed(
        db_url=db_url,
        uploads_dir=uploads_dir,
        members=0,
        jobs=3,
        batch=3,
        needle_every=0,
        seed_value=42,
    )

    # Read back through the ORM so the JSON column is decoded for us.
    import os

    os.environ.setdefault("SESSION_SECRET", "stress-seed-not-real")
    from sqlalchemy.orm import sessionmaker

    from app.models import Job

    engine = create_engine(db_url, future=True)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        jobs = session.query(Job).all()
        assert len(jobs) == 3
        with_events = [j for j in jobs if j.timeline_events]
        assert with_events, "expected at least one job with timeline_events"
        # Each event must have ISO date + event keys (matches the
        # TimelineEvent Pydantic schema).
        import re

        iso_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for j in with_events:
            for ev in j.timeline_events:
                assert set(ev.keys()) == {"date", "event"}
                assert iso_re.match(ev["date"]), f"bad ISO date: {ev['date']!r}"
                assert isinstance(ev["event"], str) and ev["event"]
    finally:
        session.close()
        engine.dispose()


def test_seed_disables_needles_when_rate_is_zero(postgres_url, uploads_dir):
    db_url = postgres_url
    stress_seed.seed(
        db_url=db_url,
        uploads_dir=uploads_dir,
        members=3,
        jobs=3,
        batch=3,
        needle_every=0,
        seed_value=1,
    )

    with _connect(db_url) as conn:
        m = conn.execute(
            text(
                "SELECT COUNT(*) FROM members WHERE resume_md LIKE '%STRESS_NEEDLE_M%'"
            )
        ).scalar()
        j = conn.execute(
            text(
                "SELECT COUNT(*) FROM jobs WHERE experience_md LIKE '%STRESS_NEEDLE_J%'"
            )
        ).scalar()
        assert m == 0
        assert j == 0
