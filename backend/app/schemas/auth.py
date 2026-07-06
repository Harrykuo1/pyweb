from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=255)


class UserResponse(BaseModel):
    id: int
    # Null for Discord-linked accounts (they have no traditional username);
    # still set for the legacy password accounts during the transition.
    username: str | None = None
    role: UserRole
    # Discord display fields, so the frontend has a name/handle to show for
    # accounts that have no username. Null for legacy password accounts.
    discord_username: str | None = None
    discord_global_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PendingLinkResponse(BaseModel):
    id: int
    discord_id: str
    discord_username: str | None = None
    discord_global_name: str | None = None
    first_seen_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResolvePendingLinkRequest(BaseModel):
    member_id: int


class RoleUpdateRequest(BaseModel):
    role: UserRole


class UpdateUsernameRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class UpdatePasswordRequest(BaseModel):
    # current_password re-authenticates the admin performing the change so a
    # forgotten unlocked session cannot silently rotate credentials.
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=1, max_length=255)


class PasswordConfirmRequest(BaseModel):
    # Re-authenticates the admin in front of a destructive action (delete
    # member, delete photo). Same shape as UpdatePasswordRequest's
    # current_password but kept as its own schema so the field name reads
    # right at the call site.
    password: str = Field(min_length=1, max_length=255)
