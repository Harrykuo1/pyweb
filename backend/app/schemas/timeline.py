from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.job import JobKindLiteral


class MemberJoinedItem(BaseModel):
    type: Literal["member_joined"] = "member_joined"
    timestamp: datetime
    member_id: int
    real_name: str
    institution: str
    position: str | None
    has_photo: bool
    photo_updated_at: datetime | None


class JobCreatedItem(BaseModel):
    type: Literal["job_created"] = "job_created"
    timestamp: datetime
    job_id: int
    company: str
    kind: JobKindLiteral
    category: str | None
    real_name: str | None
    job_year: int
    job_month: int


class EventChangedItem(BaseModel):
    type: Literal["event_created", "event_updated"]
    timestamp: datetime
    event_id: int
    title: str
    real_name: str | None


class EventCommentItem(BaseModel):
    type: Literal["event_comment_created", "event_comment_updated"]
    timestamp: datetime
    event_id: int
    title: str
    real_name: str | None
    comment_id: int
    body: str


TimelineItem = Annotated[
    MemberJoinedItem | JobCreatedItem | EventChangedItem | EventCommentItem,
    Field(discriminator="type"),
]


class TimelineResponse(BaseModel):
    items: list[TimelineItem]
    # Set by the cursor pagination path: True when at least one row exists
    # strictly older than the last item in `items`. The frontend uses this
    # to decide whether to keep fetching as the user scrolls; once it
    # flips to False, the lazy-load sentinel stops triggering.
    has_more: bool = False
