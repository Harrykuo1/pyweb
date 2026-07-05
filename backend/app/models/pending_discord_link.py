from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PendingDiscordLink(Base):
    """A guild-verified Discord identity that matched no pre-created member
    on first login. Held here for an admin to attach to the correct member;
    the row is deleted once linked.
    """

    __tablename__ = "pending_discord_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discord_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    discord_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    discord_global_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
