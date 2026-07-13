from datetime import datetime

from pydantic import BaseModel


class LikeStatusResponse(BaseModel):
    """Returned by the like / unlike endpoints so the client can update the
    heart and its count without a refetch."""

    like_count: int
    liked: bool


class LikerResponse(BaseModel):
    """One person who liked a post — enough for the FB-style "who liked this"
    list to show their avatar and name."""

    user_id: int
    display_name: str | None = None
    member_id: int | None = None
    has_photo: bool = False
    photo_updated_at: datetime | None = None
