from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    description_md: str | None = None
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
    description_md: str | None = None
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

    model_config = ConfigDict(from_attributes=True)
