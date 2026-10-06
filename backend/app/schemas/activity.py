from datetime import UTC, datetime, timedelta
from typing import Annotated

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

MAX_BATCH_ITEMS = 1000
DiscordId = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[1-9][0-9]{0,19}$")
]
Count = Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]


def _require_iso_timestamp(value):
    if not isinstance(value, (str, datetime)):
        raise ValueError("Use an ISO 8601 timestamp with a timezone")
    return value


def _utc_timestamp(value: datetime) -> datetime:
    value = value.astimezone(UTC)
    if value > datetime.now(UTC) + timedelta(minutes=5):
        raise ValueError("Timestamp is more than five minutes in the future")
    return value


ActivityTimestamp = Annotated[
    AwareDatetime,
    BeforeValidator(_require_iso_timestamp),
    AfterValidator(_utc_timestamp),
]


class MessageEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: DiscordId
    user_id: DiscordId
    channel_id: DiscordId
    sent_at: ActivityTimestamp
    reply_to_user_id: DiscordId | None = None
    text_length: Count
    attachment_count: Count


class VoiceSampleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: DiscordId
    channel_id: DiscordId
    sampled_at: ActivityTimestamp


class ActivityBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guild_id: DiscordId
    messages: list[MessageEventInput] = Field(
        default_factory=list, max_length=MAX_BATCH_ITEMS
    )
    voice_samples: list[VoiceSampleInput] = Field(
        default_factory=list, max_length=MAX_BATCH_ITEMS
    )

    @model_validator(mode="after")
    def check_size(self):
        if not 1 <= len(self.messages) + len(self.voice_samples) <= MAX_BATCH_ITEMS:
            raise ValueError(f"A batch must contain 1–{MAX_BATCH_ITEMS} total records")
        return self


class IngestCounts(BaseModel):
    inserted: int
    duplicates: int


class ActivityBatchResponse(BaseModel):
    messages: IngestCounts
    voice_samples: IngestCounts
