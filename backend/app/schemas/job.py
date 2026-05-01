from datetime import date, datetime, timezone
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_JOB_YEAR = 2000

JobKindLiteral = Literal["internship", "fulltime"]

# Cap timeline length to keep the JSON payload sane and to avoid the
# editor UI degrading on absurd inputs. 50 entries comfortably covers
# the longest realistic recruitment process; if someone genuinely
# needs more, that signals the schema needs more thought rather than
# this number going up.
TIMELINE_EVENTS_MAX = 50


class TimelineEvent(BaseModel):
    # Full ISO date so a recruitment process that spans the year
    # boundary (Dec → Jan) records honestly without having to bake
    # the year into the surrounding job context. D+N is computed at
    # display time as a simple Date subtraction, which keeps leap
    # years correct for free.
    date: date
    event: str = Field(min_length=1, max_length=200)


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
    job_month: int = Field(ge=1, le=12)
    company: str = Field(min_length=1, max_length=128)
    category: str | None = Field(default=None, min_length=1, max_length=64)
    kind: JobKindLiteral
    experience_md: str = Field(min_length=1)
    real_name: str | None = Field(default=None, min_length=1, max_length=64)
    timeline_md: str | None = None
    timeline_events: list[TimelineEvent] | None = Field(
        default=None, max_length=TIMELINE_EVENTS_MAX
    )

    @field_validator("job_year")
    @classmethod
    def _job_year_in_range(cls, v: int) -> int:
        return _validate_job_year(v)


class JobUpdate(BaseModel):
    job_year: int | None = None
    job_month: int | None = Field(default=None, ge=1, le=12)
    company: str | None = Field(default=None, min_length=1, max_length=128)
    category: str | None = Field(default=None, min_length=1, max_length=64)
    kind: JobKindLiteral | None = None
    experience_md: str | None = Field(default=None, min_length=1)
    real_name: str | None = Field(default=None, min_length=1, max_length=64)
    timeline_md: str | None = None
    timeline_events: list[TimelineEvent] | None = Field(
        default=None, max_length=TIMELINE_EVENTS_MAX
    )

    @field_validator("job_year")
    @classmethod
    def _job_year_in_range(cls, v: int | None) -> int | None:
        if v is None:
            return v
        return _validate_job_year(v)


class JobResponse(BaseModel):
    id: int
    job_year: int
    job_month: int
    company: str
    category: str | None
    kind: JobKindLiteral
    experience_md: str
    real_name: str | None
    timeline_md: str | None
    timeline_events: list[TimelineEvent] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
