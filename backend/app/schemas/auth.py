from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=255)


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class UpdateUsernameRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class UpdatePasswordRequest(BaseModel):
    # current_password re-authenticates the admin performing the change so a
    # forgotten unlocked session cannot silently rotate credentials.
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=1, max_length=255)
