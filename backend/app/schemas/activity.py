from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.job import JobKindLiteral


class MemberJoinedActivity(BaseModel):
    type: Literal["member_joined"] = "member_joined"
    timestamp: datetime
    member_id: int
    real_name: str
    institution: str
    position: str | None
    has_photo: bool
    photo_updated_at: datetime | None


class JobCreatedActivity(BaseModel):
    type: Literal["job_created"] = "job_created"
    timestamp: datetime
    job_id: int
    company: str
    kind: JobKindLiteral
    category: str | None
    real_name: str | None
    job_year: int
    job_month: int


ActivityItem = Annotated[
    MemberJoinedActivity | JobCreatedActivity,
    Field(discriminator="type"),
]


class ActivityResponse(BaseModel):
    items: list[ActivityItem]
    # Set by the cursor pagination path: True when at least one row exists
    # strictly older than the last item in `items`. The frontend uses this
    # to decide whether to keep fetching as the user scrolls; once it
    # flips to False, the lazy-load sentinel stops triggering.
    has_more: bool = False
