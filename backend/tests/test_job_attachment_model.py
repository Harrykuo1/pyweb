from datetime import datetime, timezone

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
