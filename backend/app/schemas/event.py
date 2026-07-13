from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.job import MARKDOWN_MAX_LENGTH, PostStatusLiteral

# Keep the tag set per event small enough to render as a tidy chip row
# and to bound the association-table fan-out. A genuine need for more
# than this many labels on one event signals the taxonomy wants rethinking.
EVENT_TAGS_MAX = 12
TAG_MAX_LEN = 32


def _normalize_tags(tags: list[str]) -> list[str]:
    """Trim, drop blanks, and de-duplicate case-insensitively while
    preserving first-seen order and the original casing of that first
    occurrence. Length caps are enforced by the field constraints; this
    only cleans up the contents."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in tags:
        trimmed = raw.strip()
        if not trimmed:
            continue
        key = trimmed.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(trimmed)
    return out


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    event_date: date
    location: str | None = Field(default=None, min_length=1, max_length=128)
    description_md: str | None = Field(default=None, max_length=MARKDOWN_MAX_LENGTH)
    tags: list[str] = Field(default_factory=list, max_length=EVENT_TAGS_MAX)

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, v: list[str]) -> list[str]:
        cleaned = _normalize_tags(v)
        for t in cleaned:
            if len(t) > TAG_MAX_LEN:
                raise ValueError(f"tag exceeds {TAG_MAX_LEN} characters")
        return cleaned


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    event_date: date | None = None
    location: str | None = Field(default=None, max_length=128)
    description_md: str | None = Field(default=None, max_length=MARKDOWN_MAX_LENGTH)
    tags: list[str] | None = Field(default=None, max_length=EVENT_TAGS_MAX)

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        cleaned = _normalize_tags(v)
        for t in cleaned:
            if len(t) > TAG_MAX_LEN:
                raise ValueError(f"tag exceeds {TAG_MAX_LEN} characters")
        return cleaned


class EventPhotoResponse(BaseModel):
    id: int
    event_id: int
    filename: str
    mime_type: str
    size_bytes: int
    caption: str | None
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventPhotoCaptionUpdate(BaseModel):
    caption: str | None = Field(default=None, max_length=200)


# Comments are short plain-text remarks, not posts; this bounds one comment
# to a couple of paragraphs.
COMMENT_MAX_LENGTH = 2000


class _EventCommentBody(BaseModel):
    body: str = Field(min_length=1, max_length=COMMENT_MAX_LENGTH)

    @field_validator("body")
    @classmethod
    def _strip_body(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("留言不可為空白")
        return trimmed


class EventCommentCreate(_EventCommentBody):
    pass


class EventCommentUpdate(_EventCommentBody):
    pass


class EventCommentResponse(BaseModel):
    id: int
    event_id: int
    body: str
    created_at: datetime
    # Set once the author edits; the UI shows a "已編輯" marker when present.
    edited_at: datetime | None = None
    author_display_name: str | None = None
    # The author's member profile, so the UI can show their photo as an
    # avatar. Null when the author has no profile (e.g. an admin); the two
    # photo fields then mirror the member-photo contract (has_photo gate +
    # updated-at cache-buster) used elsewhere.
    author_member_id: int | None = None
    author_has_photo: bool = False
    author_photo_updated_at: datetime | None = None
    # Only surfaced to admins (for moderation); None for everyone else.
    author_user_id: int | None = None
    # Per-viewer affordances stamped by the router: only the author edits,
    # the author or an admin deletes.
    can_edit: bool = False
    can_delete: bool = False

    model_config = ConfigDict(from_attributes=True)


class EventResponse(BaseModel):
    id: int
    title: str
    event_date: date
    location: str | None
    description_md: str | None
    created_at: datetime
    # Derived fields stamped by the router rather than ORM relationships,
    # so the list endpoint can populate them with grouped queries instead
    # of triggering a per-row lazy load.
    tags: list[str] = Field(default_factory=list)
    photo_count: int = 0
    # The cover thumbnail shown on the timeline — the earliest photo by id.
    # None when the event has no photos yet.
    cover_photo_id: int | None = None
    # Author / approval (events are never anonymous; author is the creator).
    author_display_name: str | None = None
    status: PostStatusLiteral = "accepted"
    review_reason: str | None = None
    can_edit: bool = False
    author_user_id: int | None = None

    model_config = ConfigDict(from_attributes=True)
