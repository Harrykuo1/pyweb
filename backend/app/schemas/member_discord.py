from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.discord_link import normalize_discord_handle


class MemberDiscordLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discord_id: str = Field(
        strict=True,
        pattern=r"^[1-9][0-9]{0,19}$",
        description="Discord 使用者的固定數字 ID，必須以字串傳入，不是使用者名稱。",
    )
    discord_username: str | None = Field(
        default=None,
        max_length=64,
        description="選填的顯示名稱；下次 OAuth 登入會同步正式名稱。",
    )

    @field_validator("discord_username")
    @classmethod
    def clean_username(cls, value):
        return normalize_discord_handle(value)
