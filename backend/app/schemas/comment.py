from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Comments are short plain-text remarks, not posts; this bounds one comment
# to a couple of paragraphs.
COMMENT_MAX_LENGTH = 2000


class _CommentBody(BaseModel):
    body: str = Field(min_length=1, max_length=COMMENT_MAX_LENGTH)

    @field_validator("body")
    @classmethod
    def _strip_body(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("留言不可為空白")
        return trimmed


class CommentCreate(_CommentBody):
    pass


class CommentUpdate(_CommentBody):
    pass


class CommentResponse(BaseModel):
    """Generic across post types — the client already knows which post it
    fetched the thread from, so no parent id is carried here."""

    id: int
    body: str
    created_at: datetime
    # Set once the author edits; the UI shows a "已編輯" marker when present.
    edited_at: datetime | None = None
    author_display_name: str | None = None
    # The author's member profile, so the UI can show their photo as an
    # avatar. Null when the author has no profile (e.g. an admin).
    author_member_id: int | None = None
    author_has_photo: bool = False
    author_photo_updated_at: datetime | None = None
    # Only surfaced to admins (for moderation); None for everyone else.
    author_user_id: int | None = None
    # Per-viewer affordances: only the author edits, the author or an admin
    # deletes.
    can_edit: bool = False
    can_delete: bool = False

    model_config = ConfigDict(from_attributes=True)
