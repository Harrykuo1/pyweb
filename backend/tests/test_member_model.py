from datetime import UTC, datetime

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
    assert fetched.photo_path is None
    assert fetched.resume_md is None
    assert fetched.joined_at is not None


def test_member_has_flags_default_false(db_session):
    m = Member(graduation_year=2024, real_name="A", institution="B")
    db_session.add(m)
    db_session.commit()

    fetched = db_session.query(Member).one()
    assert fetched.has_photo is False
    assert fetched.has_resume_md is False
    assert fetched.has_resume_pdf is False


def test_member_has_flags_when_populated(db_session):
    # has_photo / has_resume_pdf read the small companion columns
    # (photo_content_type, resume_pdf_updated_at) — the binary assets
    # themselves live on disk via photo_path / resume_pdf_path. Upload
    # endpoints set the companion columns in lockstep with writing the
    # file, so we mirror that invariant here.
    now = datetime.now(UTC)
    m = Member(
        graduation_year=2024,
        real_name="A",
        institution="B",
        photo_path="members/1/photo.png",
        photo_content_type="image/png",
        photo_updated_at=now,
        resume_md="# heading",
        resume_pdf_path="members/1/resume.pdf",
        resume_pdf_updated_at=now,
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


def test_member_asset_paths_default_to_none(db_session):
    m = Member(graduation_year=2024, real_name="A", institution="B")
    db_session.add(m)
    db_session.commit()

    fetched = db_session.query(Member).one()
    assert fetched.photo_path is None
    assert fetched.resume_pdf_path is None


def test_member_asset_paths_persist_when_set(db_session):
    m = Member(
        graduation_year=2024,
        real_name="A",
        institution="B",
        photo_path="members/1/photo.png",
        resume_pdf_path="members/1/resume.pdf",
    )
    db_session.add(m)
    db_session.commit()

    fetched = db_session.query(Member).one()
    assert fetched.photo_path == "members/1/photo.png"
    assert fetched.resume_pdf_path == "members/1/resume.pdf"


def test_member_links_to_user(db_session):
    from app.models import User, UserRole

    user = User(role=UserRole.MEMBER, discord_id="900")
    db_session.add(user)
    db_session.flush()

    member = Member(
        graduation_year=2024,
        real_name="測試員",
        institution="測試大學",
        user_id=user.id,
    )
    db_session.add(member)
    db_session.commit()

    assert db_session.query(Member).one().user_id == user.id


def test_member_user_id_is_unique(db_session):
    from app.models import User, UserRole

    u = User(role=UserRole.MEMBER, discord_id="901")
    db_session.add(u)
    db_session.flush()
    db_session.add(
        Member(graduation_year=2024, real_name="A", institution="X", user_id=u.id)
    )
    db_session.commit()
    db_session.add(
        Member(graduation_year=2024, real_name="B", institution="Y", user_id=u.id)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
