from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

DiscordId = Annotated[str, Field(pattern=r"^[0-9]{1,20}$")]


class AnalyticsFilters(BaseModel):
    start_date: date
    end_date: date
    timezone: str = Field(default="Asia/Taipei", min_length=1, max_length=64)
    hour_start: int = Field(default=0, ge=0, le=23)
    hour_end: int = Field(default=24, ge=1, le=24)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    user_ids: list[DiscordId] = Field(default_factory=list, max_length=50)
    channel_ids: list[DiscordId] = Field(default_factory=list, max_length=50)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("請選擇有效的時區") from None
        return value

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, value):
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("星期須介於 0（週一）至 6（週日）")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def valid_range(self):
        if not 0 <= (self.end_date - self.start_date).days <= 365:
            raise ValueError("日期範圍須為 1 至 366 天")
        if self.hour_start == self.hour_end:
            raise ValueError("起訖時段不能相同；全天請選 00:00 至 24:00")
        try:
            zone = ZoneInfo(self.timezone)
            datetime.combine(self.start_date, time.min, zone).astimezone(UTC)
            datetime.combine(
                self.end_date + timedelta(days=1), time.min, zone
            ).astimezone(UTC)
        except (OverflowError, ValueError):
            raise ValueError("日期超出支援範圍") from None
        return self


class ActivityMetrics(BaseModel):
    messages: int = 0
    voice_minutes: int = 0
    active_members: int = 0
    active_days: int = 0
    replies: int = 0
    attachments: int = 0
    text_characters: int = 0


class DailyActivity(ActivityMetrics):
    date: date


class HourlyActivity(ActivityMetrics):
    hour: int


class RhythmActivity(ActivityMetrics):
    weekday: int
    hour: int


class ActivityPerson(BaseModel):
    user_id: str
    name: str
    member_id: int | None = None


class MemberActivity(ActivityMetrics, ActivityPerson):
    pass


class ChannelActivity(ActivityMetrics):
    channel_id: str


class AnalyticsResponse(BaseModel):
    filters: AnalyticsFilters
    summary: ActivityMetrics
    daily: list[DailyActivity]
    hourly: list[HourlyActivity]
    rhythm: list[RhythmActivity]
    members: list[MemberActivity]
    channels: list[ChannelActivity]
    generated_at: datetime


class ActivityOptions(BaseModel):
    configured: bool
    users: list[ActivityPerson]
    channels: list[str]
    first_record_at: datetime | None = None
    last_record_at: datetime | None = None
    last_received_at: datetime | None = None
