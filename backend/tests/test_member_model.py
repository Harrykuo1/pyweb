import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Member


def test_create_member_with_required_fields(db_session):
    m = Member(
        graduation_year=2024,
        real_name="Alice Wang",
        institution="SWE @ Acme",
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
        institution="MS student",
        photo=blob,
        photo_content_type="image/png",
        resume_md="# Bob\n\nResume in markdown.",
        resume_pdf=b"%PDF-1.4 stub",
    )
    db_session.add(m)
    db_session.commit()

    fetched = db_session.query(Member).one()
    assert fetched.photo == blob
    assert fetched.photo_content_type == "image/png"
    assert fetched.resume_pdf == b"%PDF-1.4 stub"
    assert "markdown" in fetched.resume_md


def test_member_has_flags_default_false(db_session):
    m = Member(graduation_year=2024, real_name="A", institution="B")
    db_session.add(m)
    db_session.commit()

    fetched = db_session.query(Member).one()
    assert fetched.has_photo is False
    assert fetched.has_resume_md is False
    assert fetched.has_resume_pdf is False


def test_member_has_flags_when_populated(db_session):
    m = Member(
        graduation_year=2024,
        real_name="A",
        institution="B",
        photo=b"\x89PNG",
        resume_md="# heading",
        resume_pdf=b"%PDF",
    )
    db_session.add(m)
    db_session.commit()

    fetched = db_session.query(Member).one()
    assert fetched.has_photo is True
    assert fetched.has_resume_md is True
    assert fetched.has_resume_pdf is True


def test_member_has_resume_md_false_for_whitespace_only(db_session):
    m = Member(
        graduation_year=2024,
        real_name="A",
        institution="B",
        resume_md="   \n\t",
    )
    db_session.add(m)
    db_session.commit()

    assert db_session.query(Member).one().has_resume_md is False


def test_member_required_field_real_name_missing_raises(db_session):
    m = Member(graduation_year=2022, institution="Engineer")
    db_session.add(m)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_member_position_optional_defaults_to_none(db_session):
    m = Member(graduation_year=2024, real_name="A", institution="NYCU")
    db_session.add(m)
    db_session.commit()

    assert db_session.query(Member).one().position is None


def test_member_position_persists_when_set(db_session):
    m = Member(
        graduation_year=2024,
        real_name="A",
        institution="NYCU",
        position="CS dept, MS",
    )
    db_session.add(m)
    db_session.commit()

    assert db_session.query(Member).one().position == "CS dept, MS"


def test_member_required_field_institution_missing_raises(db_session):
    m = Member(graduation_year=2024, real_name="A")
    db_session.add(m)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
