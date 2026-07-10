from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemberCreate(BaseModel):
    graduation_year: int = Field(ge=1900, le=2100)
    real_name: str = Field(min_length=1, max_length=64)
    institution: str = Field(min_length=1, max_length=128)
    position: str | None = Field(default=None, min_length=1, max_length=128)
    resume_md: str | None = None
    discord_username: str | None = Field(default=None, max_length=64)
    joined_at: datetime | None = None


class MemberSelfCreate(BaseModel):
    graduation_year: int = Field(ge=1900, le=2100)
    real_name: str = Field(min_length=1, max_length=64)
    institution: str = Field(min_length=1, max_length=128)
    position: str | None = Field(default=None, min_length=1, max_length=128)
    resume_md: str | None = None


class MemberUpdate(BaseModel):
    graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    real_name: str | None = Field(default=None, min_length=1, max_length=64)
    institution: str | None = Field(default=None, min_length=1, max_length=128)
    position: str | None = Field(default=None, min_length=1, max_length=128)
    resume_md: str | None = None
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
