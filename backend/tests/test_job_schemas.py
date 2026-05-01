from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import Job, JobKind
from app.schemas import (
    JobCreate,
    JobResponse,
    JobUpdate,
    ListResponse,
)


def _current_max_year() -> int:
    return datetime.now(timezone.utc).year + 1


def _payload(**overrides):
    base = {
        "job_year": 2025,
        "job_month": 6,
        "company": "Acme",
        "kind": "internship",
        "experience_md": "x",
    }
    base.update(overrides)
    return base


def test_job_create_with_required_fields():
    payload = JobCreate(**_payload(experience_md="## interview\n- foo"))
    assert payload.kind == "internship"
    assert payload.real_name is None
    assert payload.timeline_md is None


def test_job_create_accepts_fulltime_kind():
    payload = JobCreate(**_payload(kind="fulltime"))
    assert payload.kind == "fulltime"


def test_job_create_accepts_optional_fields():
    payload = JobCreate(
        **_payload(real_name="Carol", timeline_md="| d | e |\n|---|---|"),
    )
    assert payload.real_name == "Carol"
    assert "d" in payload.timeline_md


def test_job_create_category_defaults_to_none():
    assert JobCreate(**_payload()).category is None


def test_job_create_accepts_category():
    assert JobCreate(**_payload(category="DevOps")).category == "DevOps"


@pytest.mark.parametrize("bad", ["", "x" * 65])
def test_job_create_rejects_invalid_category(bad):
    with pytest.raises(ValidationError):
        JobCreate(**_payload(category=bad))


@pytest.mark.parametrize(
    "field,bad",
    [
        ("company", ""),
        ("company", "x" * 129),
        ("experience_md", ""),
        ("real_name", ""),
        ("real_name", "x" * 65),
    ],
)
def test_job_create_field_constraints(field, bad):
    payload = _payload()
    payload[field] = bad
    with pytest.raises(ValidationError):
        JobCreate(**payload)


def test_job_create_rejects_missing_kind():
    payload = _payload()
    del payload["kind"]
    with pytest.raises(ValidationError):
        JobCreate(**payload)


@pytest.mark.parametrize("bad", ["", "part-time", "INTERNSHIP", "intern"])
def test_job_create_rejects_invalid_kind(bad):
    with pytest.raises(ValidationError):
        JobCreate(**_payload(kind=bad))


def test_job_create_rejects_year_below_min():
    with pytest.raises(ValidationError):
        JobCreate(**_payload(job_year=1999))


def test_job_create_rejects_year_above_max():
    with pytest.raises(ValidationError):
        JobCreate(**_payload(job_year=_current_max_year() + 1))


def test_job_create_accepts_year_at_max_boundary():
    JobCreate(**_payload(job_year=_current_max_year()))


def test_job_create_accepts_year_at_min_boundary():
    JobCreate(**_payload(job_year=2000))


def test_job_create_rejects_missing_month():
    payload = _payload()
    del payload["job_month"]
    with pytest.raises(ValidationError):
        JobCreate(**payload)


@pytest.mark.parametrize("bad", [0, 13, -1, 100])
def test_job_create_rejects_out_of_range_month(bad):
    with pytest.raises(ValidationError):
        JobCreate(**_payload(job_month=bad))


@pytest.mark.parametrize("good", [1, 6, 12])
def test_job_create_accepts_month_at_boundaries(good):
    payload = JobCreate(**_payload(job_month=good))
    assert payload.job_month == good


def test_job_update_all_fields_optional():
    upd = JobUpdate()
    assert upd.job_year is None
    assert upd.job_month is None
    assert upd.company is None
    assert upd.kind is None
    assert upd.experience_md is None
    assert upd.real_name is None
    assert upd.timeline_md is None


def test_job_update_rejects_out_of_range_month_when_provided():
    with pytest.raises(ValidationError):
        JobUpdate(job_month=13)


def test_job_update_partial_payload_excludes_unset():
    upd = JobUpdate(company="New Co")
    assert upd.model_dump(exclude_unset=True) == {"company": "New Co"}


def test_job_update_validates_year_when_provided():
    with pytest.raises(ValidationError):
        JobUpdate(job_year=1500)


def test_job_update_rejects_empty_company_when_provided():
    with pytest.raises(ValidationError):
        JobUpdate(company="")


def test_job_update_accepts_category():
    upd = JobUpdate(category="Backend")
    assert upd.category == "Backend"


def test_job_update_rejects_oversized_category():
    with pytest.raises(ValidationError):
        JobUpdate(category="x" * 65)


def test_job_update_rejects_invalid_kind_when_provided():
    with pytest.raises(ValidationError):
        JobUpdate(kind="freelance")


def test_job_response_from_orm_object():
    now = datetime.now(timezone.utc)
    j = Job(
        id=1,
        job_year=2025,
        job_month=6,
        company="Acme",
        kind=JobKind.INTERNSHIP,
        experience_md="# hi",
        real_name=None,
        timeline_md=None,
        created_at=now,
    )
    resp = JobResponse.model_validate(j)
    assert resp.id == 1
    assert resp.job_month == 6
    assert resp.kind == "internship"
    assert resp.real_name is None
    assert resp.category is None


def test_job_response_exposes_category_when_set():
    now = datetime.now(timezone.utc)
    j = Job(
        id=3,
        job_year=2025,
        job_month=1,
        company="Acme",
        category="Frontend",
        kind=JobKind.INTERNSHIP,
        experience_md="x",
        created_at=now,
    )
    assert JobResponse.model_validate(j).category == "Frontend"


def test_job_response_from_fulltime_orm_object():
    now = datetime.now(timezone.utc)
    j = Job(
        id=2,
        job_year=2024,
        job_month=11,
        company="Globex",
        kind=JobKind.FULLTIME,
        experience_md="x",
        created_at=now,
    )
    resp = JobResponse.model_validate(j)
    assert resp.kind == "fulltime"


def test_list_response_carries_items_and_total():
    now = datetime.now(timezone.utc)
    item = JobResponse(
        id=1,
        job_year=2025,
        job_month=3,
        company="Acme",
        category=None,
        kind="internship",
        experience_md="x",
        real_name=None,
        timeline_md=None,
        timeline_events=None,
        created_at=now,
    )
    page = ListResponse[JobResponse](items=[item], total=1)
    assert page.total == 1
    assert page.items[0].kind == "internship"
