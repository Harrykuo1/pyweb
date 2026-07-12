from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Upper bound for the free-text resume markdown. Generous for real content
# while capping a single authenticated write from stuffing the ~256 MB nginx
# body limit into one text column.
MARKDOWN_MAX_LENGTH = 100_000


class MemberCreate(BaseModel):
    graduation_year: int = Field(ge=1900, le=2100)
    real_name: str = Field(min_length=1, max_length=64)
    institution: str = Field(min_length=1, max_length=128)
    position: str | None = Field(default=None, min_length=1, max_length=128)
    resume_md: str | None = Field(default=None, max_length=MARKDOWN_MAX_LENGTH)
    discord_username: str | None = Field(default=None, max_length=64)
    joined_at: datetime | None = None


class MemberSelfCreate(BaseModel):
    graduation_year: int = Field(ge=1900, le=2100)
    real_name: str = Field(min_length=1, max_length=64)
    institution: str = Field(min_length=1, max_length=128)
    position: str | None = Field(default=None, min_length=1, max_length=128)
    resume_md: str | None = Field(default=None, max_length=MARKDOWN_MAX_LENGTH)


class MemberUpdate(BaseModel):
    graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    real_name: str | None = Field(default=None, min_length=1, max_length=64)
    institution: str | None = Field(default=None, min_length=1, max_length=128)
    position: str | None = Field(default=None, min_length=1, max_length=128)
    resume_md: str | None = Field(default=None, max_length=MARKDOWN_MAX_LENGTH)
    joined_at: datetime | None = None
    discord_username: str | None = Field(default=None, max_length=64)


class MemberResponse(BaseModel):
    id: int
    graduation_year: int
    real_name: str
    institution: str
    position: str | None
    resume_md: str | None
    joined_at: datetime
    has_photo: bool
    has_resume_md: bool
    has_resume_pdf: bool
    photo_updated_at: datetime | None
    resume_pdf_updated_at: datetime | None
    account_status: str = "legacy"
    is_active: bool = True
    account_id: int | None = None
    account_discord_username: str | None = None

    model_config = ConfigDict(from_attributes=True)
