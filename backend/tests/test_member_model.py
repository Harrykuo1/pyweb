import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Member


def test_create_member_with_required_fields(db_session):
    m = Member(
        graduation_year=2024,
        real_name="Alice Wang",
        current_position="SWE @ Acme",
    )
    db_session.add(m)
    db_session.commit()

    fetched = db_session.query(Member).one()
    assert fetched.graduation_year == 2024
    assert fetched.real_name == "Alice Wang"
    assert fetched.photo is None
    assert fetched.resume_md is None
    assert fetched.joined_at is not None


def test_create_member_with_photo_blob_and_resume(db_session):
    blob = b"\x89PNG\r\n\x1a\nfake-image-bytes"
    m = Member(
        graduation_year=2023,
        real_name="Bob",
        current_position="MS student",
        photo=blob,
        resume_md="# Bob\n\nResume in markdown.",
    )
    db_session.add(m)
    db_session.commit()

    fetched = db_session.query(Member).one()
    assert fetched.photo == blob
    assert "markdown" in fetched.resume_md


def test_member_required_field_real_name_missing_raises(db_session):
    m = Member(graduation_year=2022, current_position="Engineer")
    db_session.add(m)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
