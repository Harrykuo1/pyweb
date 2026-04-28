from datetime import datetime, timezone
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_JOB_YEAR = 2000

JobKindLiteral = Literal["internship", "fulltime"]


def _max_job_year() -> int:
    return datetime.now(timezone.utc).year + 1


def _validate_job_year(value: int) -> int:
    if value < MIN_JOB_YEAR or value > _max_job_year():
        raise ValueError(
            f"job_year must be between {MIN_JOB_YEAR} and {_max_job_year()}"
        )
    return value


class JobCreate(BaseModel):
    job_year: int
    company: str = Field(min_length=1, max_length=128)
    kind: JobKindLiteral
    experience_md: str = Field(min_length=1)
    real_name: str | None = Field(default=None, min_length=1, max_length=64)
    timeline_md: str | None = None

    @field_validator("job_year")
    @classmethod
    def _job_year_in_range(cls, v: int) -> int:
        return _validate_job_year(v)


class JobUpdate(BaseModel):
    job_year: int | None = None
    company: str | None = Field(default=None, min_length=1, max_length=128)
    kind: JobKindLiteral | None = None
    experience_md: str | None = Field(default=None, min_length=1)
    real_name: str | None = Field(default=None, min_length=1, max_length=64)
    timeline_md: str | None = None

    @field_validator("job_year")
    @classmethod
    def _job_year_in_range(cls, v: int | None) -> int | None:
        if v is None:
            return v
        return _validate_job_year(v)


class JobResponse(BaseModel):
    id: int
    job_year: int
    company: str
    kind: JobKindLiteral
    experience_md: str
    real_name: str | None
    timeline_md: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
