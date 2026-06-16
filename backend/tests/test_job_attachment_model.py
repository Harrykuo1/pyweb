from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Job, JobAttachment, JobKind


def _make_job(db_session):
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


def test_attachment_row_roundtrips(db_session):
    job = _make_job(db_session)

    db_session.add(
        JobAttachment(
            job_id=job.id,
            filename="report.pdf",
            mime_type="application/pdf",
            size_bytes=1234,
            uploaded_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    rows = db_session.query(JobAttachment).filter_by(job_id=job.id).all()
    assert len(rows) == 1
    assert rows[0].filename == "report.pdf"
    assert rows[0].mime_type == "application/pdf"
    assert rows[0].size_bytes == 1234


def test_two_jobs_may_share_an_original_filename(db_session):
    """The subfolder-per-job storage layout means original filenames
    are scoped to a job, so two jobs each having their own 'cv.pdf'
    is fine — no uniqueness constraint at the table level."""
    job_a = _make_job(db_session)
    job_b = _make_job(db_session)

    db_session.add_all(
        [
            JobAttachment(
                job_id=job_a.id,
                filename="cv.pdf",
                mime_type="application/pdf",
                size_bytes=1,
                uploaded_at=datetime.now(timezone.utc),
            ),
            JobAttachment(
                job_id=job_b.id,
                filename="cv.pdf",
                mime_type="application/pdf",
                size_bytes=2,
                uploaded_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db_session.commit()

    assert db_session.query(JobAttachment).count() == 2


def test_attachment_fk_declares_cascade_delete():
    # The DB-level guarantee that deleting a job removes its attachments is
    # ondelete="CASCADE" on the FK. Lock the declaration so a refactor can't
    # silently drop it (deterministic; no PRAGMA dependency).
    fk = next(iter(JobAttachment.__table__.c.job_id.foreign_keys))
    assert fk.ondelete == "CASCADE"


def test_attachment_filename_required(db_session):
    job = _make_job(db_session)
    db_session.add(
        JobAttachment(
            job_id=job.id,
            mime_type="application/pdf",
            size_bytes=1,
            uploaded_at=datetime.now(timezone.utc),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_job_cascades_to_attachments():
    # SQLite only honors ON DELETE CASCADE with foreign_keys ON, which the
    # app enables in app/database.py but the shared in-memory test engine
    # does not. Use a local FK-enabled engine so this exercises the real
    # production cascade behavior.
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app import models  # noqa: F401  (register tables on Base.metadata)
    from app.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        job = Job(
            job_year=2026, job_month=5, company="Acme",
            kind=JobKind.INTERNSHIP, experience_md="x",
        )
        s.add(job)
        s.commit()
        s.add(
            JobAttachment(
                job_id=job.id, filename="cv.pdf", mime_type="application/pdf",
                size_bytes=1, uploaded_at=datetime.now(timezone.utc),
            )
        )
        s.commit()
        assert s.query(JobAttachment).count() == 1

        s.delete(job)
        s.commit()
        assert s.query(JobAttachment).count() == 0  # cascaded with the job
    finally:
        s.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
