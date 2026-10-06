from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.activity import ActivityTimestamp, DiscordId


def _valid_name(value):
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Channel name must not contain control characters")
    return value


ChannelName = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(_valid_name),
]


class ChannelNameUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: ChannelName


class ChannelNameRecord(ChannelNameUpdate):
    channel_id: DiscordId
    observed_at: ActivityTimestamp


class ChannelNamesBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    guild_id: DiscordId
    channels: list[ChannelNameRecord] = Field(min_length=1, max_length=1000)


class ChannelNamesResult(BaseModel):
    updated: int
    unchanged: int


class ChannelNameResponse(BaseModel):
    channel_id: str
    name: str
    updated_at: datetime
