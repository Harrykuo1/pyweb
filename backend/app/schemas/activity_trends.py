from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.activity_analytics import ActivityPerson, AnalyticsFilters, DiscordId


class MemberTrendFilters(BaseModel):
    end_date: date
    window_days: Literal[7, 14, 30] = 7
    timezone: str = Field(default="Asia/Taipei", min_length=1, max_length=64)
    hour_start: int = Field(default=0, ge=0, le=23)
    hour_end: int = Field(default=24, ge=1, le=24)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    channel_ids: list[DiscordId] = Field(default_factory=list, max_length=50)
    user_ids: list[DiscordId] = Field(min_length=1, max_length=6)

    @field_validator("window_days", mode="before")
    @classmethod
    def parse_window(cls, value):
        return int(value) if value in ("7", "14", "30") else value

    @model_validator(mode="after")
    def valid_filters(self):
        if self.end_date < date(1970, 1, 1):
            raise ValueError("結束日期須在 1970 年以後")
        AnalyticsFilters(
            start_date=self.end_date, **self.model_dump(exclude={"window_days"})
        )
        self.user_ids = list(dict.fromkeys(self.user_ids))
        return self


class MemberTrendPoint(BaseModel):
    date: date
    messages: int
    voice_minutes: int
    messages_avg7: float
    voice_minutes_avg7: float


class MemberTrendSeries(ActivityPerson):
    daily: list[MemberTrendPoint]
    current_messages: int
    previous_messages: int
    current_voice_minutes: int
    previous_voice_minutes: int
    current_messages_rate: float
    previous_messages_rate: float
    current_voice_minutes_rate: float
    previous_voice_minutes_rate: float
    messages_change_percent: float | None
    voice_minutes_change_percent: float | None


class MemberTrendsResponse(BaseModel):
    timezone: str
    window_days: int
    current_start: date
    current_end: date
    previous_start: date
    previous_end: date
    eligible_current_days: int
    eligible_previous_days: int
    excluded_today: bool
    series: list[MemberTrendSeries]
    generated_at: datetime
