import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Job, JobComment, JobKind, JobLike, PostStatus, User, UserRole


def _job_and_user(db_session):
    user = User(role=UserRole.MEMBER, discord_id="900")
    db_session.add(user)
    db_session.flush()
    job = Job(
        job_year=2024,
        job_month=6,
        company="Acme",
        kind=JobKind.INTERNSHIP,
        experience_md="心得",
        status=PostStatus.ACCEPTED,
        author_user_id=user.id,
    )
    db_session.add(job)
    db_session.flush()
    return job, user


def test_job_comment_persists_and_cascades(db_session):
    job, user = _job_and_user(db_session)
    db_session.add(JobComment(job_id=job.id, author_user_id=user.id, body="讚"))
    db_session.commit()
    assert db_session.query(JobComment).count() == 1

    db_session.delete(job)
    db_session.commit()
    assert db_session.query(JobComment).count() == 0


def test_job_like_persists_and_cascades(db_session):
    job, user = _job_and_user(db_session)
    db_session.add(JobLike(job_id=job.id, user_id=user.id))
    db_session.commit()
    assert db_session.query(JobLike).count() == 1

    db_session.delete(job)
    db_session.commit()
    assert db_session.query(JobLike).count() == 0


def test_duplicate_job_like_rejected(db_session):
    job, user = _job_and_user(db_session)
    db_session.add(JobLike(job_id=job.id, user_id=user.id))
    db_session.commit()
    db_session.add(JobLike(job_id=job.id, user_id=user.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
