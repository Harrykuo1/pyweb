import pytest
from sqlalchemy.exc import IntegrityError, StatementError

from app.models import Internship, JobKind


def test_create_internship_with_required_fields(db_session):
    i = Internship(
        job_year=2025,
        company="Acme Corp",
        kind=JobKind.INTERNSHIP,
        experience_md="## Interview\n\n- Data structures\n- System design",
    )
    db_session.add(i)
    db_session.commit()

    fetched = db_session.query(Internship).one()
    assert fetched.company == "Acme Corp"
    assert fetched.kind is JobKind.INTERNSHIP
    assert fetched.real_name is None
    assert fetched.timeline_md is None
    assert fetched.created_at is not None


def test_create_fulltime_internship_with_optional_fields(db_session):
    i = Internship(
        job_year=2024,
        company="Globex",
        kind=JobKind.FULLTIME,
        experience_md="experience",
        real_name="Carol",
        timeline_md="| date | event |\n|---|---|\n| 5/1 | apply |",
    )
    db_session.add(i)
    db_session.commit()

    fetched = db_session.query(Internship).one()
    assert fetched.kind is JobKind.FULLTIME
    assert fetched.real_name == "Carol"
    assert "apply" in fetched.timeline_md


def test_internship_required_field_company_missing_raises(db_session):
    i = Internship(job_year=2025, kind=JobKind.INTERNSHIP, experience_md="x")
    db_session.add(i)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_internship_kind_required(db_session):
    i = Internship(job_year=2025, company="Acme", experience_md="x")
    db_session.add(i)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_internship_kind_rejects_invalid_value(db_session):
    i = Internship(
        job_year=2025,
        company="Acme",
        kind="not-a-real-kind",
        experience_md="x",
    )
    db_session.add(i)
    with pytest.raises((StatementError, IntegrityError)):
        db_session.commit()
    db_session.rollback()
