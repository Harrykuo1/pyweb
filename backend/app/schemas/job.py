from datetime import UTC, date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_JOB_YEAR = 2000

JobKindLiteral = Literal["internship", "fulltime"]
PostStatusLiteral = Literal["pending", "accepted", "rejected"]

# Cap timeline length to keep the JSON payload sane and to avoid the
# editor UI degrading on absurd inputs. 50 entries comfortably covers
# the longest realistic recruitment process; if someone genuinely
# needs more, that signals the schema needs more thought rather than
# this number going up.
TIMELINE_EVENTS_MAX = 50
# Upper bound for free-text markdown bodies. Generous for real content
# (largest existing post is < 1 KB) while capping a single authenticated
# write from stuffing the ~256 MB nginx body limit into one text column.
MARKDOWN_MAX_LENGTH = 100_000


class TimelineEvent(BaseModel):
    # Full ISO date so a recruitment process that spans the year
    # boundary (Dec → Jan) records honestly without having to bake
    # the year into the surrounding job context. D+N is computed at
    # display time as a simple Date subtraction, which keeps leap
    # years correct for free.
    date: date
    event: str = Field(min_length=1, max_length=200)


def _max_job_year() -> int:
    return datetime.now(UTC).year + 1


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
    experience_md: str = Field(min_length=1, max_length=MARKDOWN_MAX_LENGTH)
    # Admin free-text author fallback (when not picking a member subject).
    real_name: str | None = Field(default=None, min_length=1, max_length=64)
    # Admin-only: the member this post is about. Ignored for members (their
    # subject is always themselves).
    subject_member_id: int | None = None
    is_anonymous: bool = False
    timeline_md: str | None = Field(default=None, max_length=MARKDOWN_MAX_LENGTH)
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
    experience_md: str | None = Field(
        default=None, min_length=1, max_length=MARKDOWN_MAX_LENGTH
    )
    real_name: str | None = Field(default=None, min_length=1, max_length=64)
    # Admin-only on update; the router pops these for non-admin editors.
    subject_member_id: int | None = None
    is_anonymous: bool | None = None
    timeline_md: str | None = Field(default=None, max_length=MARKDOWN_MAX_LENGTH)
    timeline_events: list[TimelineEvent] | None = Field(
        default=None, max_length=TIMELINE_EVENTS_MAX
    )

    @field_validator("job_year")
    @classmethod
    def _job_year_in_range(cls, v: int | None) -> int | None:
        if v is None:
            return v
        return _validate_job_year(v)


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class JobResponse(BaseModel):
    id: int
    job_year: int
    job_month: int
    company: str
    category: str | None
    kind: JobKindLiteral
    experience_md: str
    timeline_md: str | None
    timeline_events: list[TimelineEvent] | None
    created_at: datetime
    # Populated by the jobs router via a per-call COUNT query, not an
    # ORM relationship — keeps the Job model decoupled from the
    # attachments subsystem.
    attachment_count: int = 0
    # --- author / visibility, role-filtered by app.core.job_serialize ---
    # Public-safe display name. None => anonymous to this viewer (§8).
    display_name: str | None = None
    is_anonymous: bool = False
    status: PostStatusLiteral = "accepted"
    # Present only when the viewer may see identity (non-anonymous, or admin).
    subject_member_id: int | None = None
    # Admin-only: the real poster; None for everyone else.
    author_user_id: int | None = None
    # Admin or the post's owner only.
    review_reason: str | None = None
    can_edit: bool = False
    # Heart count + whether the current viewer hearted it, stamped by the
    # jobs router with grouped queries.
    like_count: int = 0
    liked_by_me: bool = False

    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
