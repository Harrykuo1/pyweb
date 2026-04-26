from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import Member
from app.schemas import MemberCreate, MemberResponse, MemberUpdate


def test_member_create_with_required_fields():
    payload = MemberCreate(
        graduation_year=2024,
        real_name="Alice Wang",
        current_position="SWE @ Acme",
    )
    assert payload.resume_md is None
    assert payload.joined_at is None


def test_member_create_with_iso_datetime_string():
    payload = MemberCreate(
        graduation_year=2024,
        real_name="Alice",
        current_position="SWE",
        joined_at="2024-05-01",
    )
    assert payload.joined_at == datetime(2024, 5, 1, 0, 0)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("graduation_year", 1899),
        ("graduation_year", 2101),
        ("real_name", ""),
        ("current_position", ""),
    ],
)
def test_member_create_field_constraints(field, bad):
    payload = {
        "graduation_year": 2024,
        "real_name": "Alice",
        "current_position": "SWE",
    }
    payload[field] = bad
    with pytest.raises(ValidationError):
        MemberCreate(**payload)


def test_member_update_all_fields_optional():
    upd = MemberUpdate()
    assert upd.graduation_year is None
    assert upd.real_name is None
    assert upd.current_position is None
    assert upd.resume_md is None
    assert upd.joined_at is None


def test_member_update_partial_payload():
    upd = MemberUpdate(real_name="New Name")
    assert upd.real_name == "New Name"
    # Other fields stay None and the model_dump excludes unset fields.
    assert upd.model_dump(exclude_unset=True) == {"real_name": "New Name"}


def test_member_update_rejects_empty_string_when_provided():
    with pytest.raises(ValidationError):
        MemberUpdate(real_name="")


def test_member_response_from_orm_object():
    now = datetime.now(timezone.utc)
    m = Member(
        id=1,
        graduation_year=2023,
        real_name="Alice",
        current_position="SWE",
        resume_md="# hi",
        joined_at=now,
    )
    resp = MemberResponse.model_validate(m)
    assert resp.id == 1
    assert resp.graduation_year == 2023
    assert resp.resume_md == "# hi"
    assert resp.has_resume_md is True
    assert resp.has_photo is False
    assert resp.has_resume_pdf is False


def test_member_response_omits_binary_fields():
    m = Member(
        id=2,
        graduation_year=2022,
        real_name="Bob",
        current_position="SWE",
        photo=b"\x00\x01\x02-secret-bytes",
        photo_content_type="image/png",
        resume_pdf=b"%PDF-1.4 secret",
        joined_at=datetime.now(timezone.utc),
    )
    dumped = MemberResponse.model_validate(m).model_dump()
    assert "photo" not in dumped
    assert "resume_pdf" not in dumped
    assert "photo_content_type" not in dumped
    assert dumped["has_photo"] is True
    assert dumped["has_resume_pdf"] is True
