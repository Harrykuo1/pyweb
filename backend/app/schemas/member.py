from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemberCreate(BaseModel):
    graduation_year: int = Field(ge=1900, le=2100)
    real_name: str = Field(min_length=1, max_length=64)
    current_position: str = Field(min_length=1, max_length=255)
    resume_md: str | None = None
    joined_at: datetime | None = None


class MemberUpdate(BaseModel):
    graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    real_name: str | None = Field(default=None, min_length=1, max_length=64)
    current_position: str | None = Field(
        default=None, min_length=1, max_length=255
    )
    resume_md: str | None = None
    joined_at: datetime | None = None


class MemberResponse(BaseModel):
    id: int
    graduation_year: int
    real_name: str
    current_position: str
    resume_md: str | None
    joined_at: datetime
    has_photo: bool
    has_resume_md: bool
    has_resume_pdf: bool

    model_config = ConfigDict(from_attributes=True)
