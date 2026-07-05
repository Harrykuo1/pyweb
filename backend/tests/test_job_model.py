import pytest
from sqlalchemy.exc import IntegrityError, StatementError

from app.models import Job, JobKind


def test_create_internship_job_with_required_fields(db_session):
    j = Job(
        job_year=2025,
        job_month=6,
        company="Acme Corp",
        kind=JobKind.INTERNSHIP,
        experience_md="## Interview\n\n- Data structures\n- System design",
    )
    db_session.add(j)
    db_session.commit()

    fetched = db_session.query(Job).one()
    assert fetched.company == "Acme Corp"
    assert fetched.job_year == 2025
    assert fetched.job_month == 6
    assert fetched.kind is JobKind.INTERNSHIP
    assert fetched.real_name is None
    assert fetched.timeline_md is None
    assert fetched.created_at is not None


def test_create_fulltime_job_with_optional_fields(db_session):
    j = Job(
        job_year=2024,
        job_month=11,
        company="Globex",
        kind=JobKind.FULLTIME,
        experience_md="experience",
        real_name="Carol",
        timeline_md="| date | event |\n|---|---|\n| 5/1 | apply |",
    )
    db_session.add(j)
    db_session.commit()

    fetched = db_session.query(Job).one()
    assert fetched.kind is JobKind.FULLTIME
    assert fetched.job_month == 11
    assert fetched.real_name == "Carol"
    assert "apply" in fetched.timeline_md


def test_job_required_field_company_missing_raises(db_session):
    j = Job(
        job_year=2025,
        job_month=1,
        kind=JobKind.INTERNSHIP,
        experience_md="x",
    )
    db_session.add(j)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_job_month_required(db_session):
    j = Job(
        job_year=2025,
        company="Acme",
        kind=JobKind.INTERNSHIP,
        experience_md="x",
    )
    db_session.add(j)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_job_kind_required(db_session):
    j = Job(
        job_year=2025,
        job_month=1,
        company="Acme",
        experience_md="x",
    )
    db_session.add(j)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_job_category_optional_defaults_to_none(db_session):
    j = Job(
        job_year=2025,
        job_month=6,
        company="Acme",
        kind=JobKind.INTERNSHIP,
        experience_md="x",
    )
    db_session.add(j)
    db_session.commit()

    assert db_session.query(Job).one().category is None


def test_job_category_persists_when_set(db_session):
    j = Job(
        job_year=2025,
        job_month=6,
        company="Acme",
        category="DevOps",
        kind=JobKind.INTERNSHIP,
        experience_md="x",
    )
    db_session.add(j)
    db_session.commit()

    assert db_session.query(Job).one().category == "DevOps"


def test_job_kind_rejects_invalid_value(db_session):
    j = Job(
        job_year=2025,
        job_month=1,
        company="Acme",
        kind="not-a-real-kind",
        experience_md="x",
    )
    db_session.add(j)
    with pytest.raises((StatementError, IntegrityError)):
        db_session.commit()
    db_session.rollback()


def test_job_experience_md_required(db_session):
    j = Job(job_year=2025, job_month=1, company="Acme", kind=JobKind.INTERNSHIP)
    db_session.add(j)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_job_year_required(db_session):
    j = Job(job_month=1, company="Acme", kind=JobKind.INTERNSHIP, experience_md="x")
    db_session.add(j)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_job_new_columns_default_and_link(db_session):
    from app.models import Member, PostStatus, User, UserRole

    author = User(role=UserRole.MEMBER, discord_id="700")
    db_session.add(author)
    db_session.flush()
    subject = Member(
        graduation_year=2024, real_name="王小明", institution="X", user_id=author.id
    )
    db_session.add(subject)
    db_session.flush()

    job = Job(
        job_year=2024,
        job_month=3,
        company="Foo",
        kind=JobKind.INTERNSHIP,
        experience_md="hi",
        subject_member_id=subject.id,
        author_user_id=author.id,
        is_anonymous=True,
        status=PostStatus.PENDING,
    )
    db_session.add(job)
    db_session.commit()

    fetched = db_session.query(Job).one()
    assert fetched.status is PostStatus.PENDING
    assert fetched.is_anonymous is True
    assert fetched.subject_member_id == subject.id
    assert fetched.author_user_id == author.id
    assert fetched.reviewed_at is None


def test_job_status_rejects_invalid(db_session):
    from sqlalchemy.exc import SQLAlchemyError

    job = Job(
        job_year=2024,
        job_month=3,
        company="Foo",
        kind=JobKind.INTERNSHIP,
        experience_md="hi",
        status="approved",  # not a PostStatus value
    )
    db_session.add(job)
    with pytest.raises(SQLAlchemyError):
        db_session.commit()
    db_session.rollback()
