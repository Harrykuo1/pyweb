from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.db_types import UTCDateTime


class MessageEvent(Base):
    __tablename__ = "message_events"
    __table_args__ = (
        CheckConstraint("text_length >= 0", name="ck_message_text_length"),
        CheckConstraint("attachment_count >= 0", name="ck_message_attachment_count"),
        Index("ix_message_events_guild_time", "guild_id", "sent_at"),
        Index("ix_message_events_guild_user_time", "guild_id", "user_id", "sent_at"),
        Index(
            "ix_message_events_guild_channel_time", "guild_id", "channel_id", "sent_at"
        ),
    )

    guild_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    # Discord members need not have registered on this site.
    user_id: Mapped[str] = mapped_column(String(20), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(20), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True), nullable=False
    )
    reply_to_user_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    text_length: Mapped[int] = mapped_column(Integer, nullable=False)
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class VoiceSample(Base):
    __tablename__ = "voice_samples"
    __table_args__ = (
        Index("ix_voice_samples_guild_time", "guild_id", "sampled_at"),
        Index(
            "ix_voice_samples_guild_channel_time",
            "guild_id",
            "channel_id",
            "sampled_at",
        ),
    )

    guild_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    sampled_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True), primary_key=True
    )
    channel_id: Mapped[str] = mapped_column(String(20), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class ActivityIngestToken(Base):
    __tablename__ = "activity_ingest_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    guild_id: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(timezone=True), nullable=True
    )


class ActivityChannel(Base):
    __tablename__ = "activity_channels"

    guild_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True), nullable=False
    )
