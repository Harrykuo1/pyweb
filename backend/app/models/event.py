from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    # The day the community gathering happened. Drives the timeline
    # ordering on the events page; stored as a bare date because the
    # hour rarely matters for "we went out / had dinner / competed".
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Ordered children. delete-orphan keeps the association rows in lockstep
    # with the parent so deleting an event clears its tags/photos in one go;
    # the on-disk photo files are cleaned up explicitly by the delete handler.
    tags: Mapped[list["EventTag"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventTag.name",
    )
    photos: Mapped[list["EventPhoto"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventPhoto.id",
    )


class EventTag(Base):
    __tablename__ = "event_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Free-form label ("春酒", "桌遊", "北部場"). No fixed vocabulary —
    # the events page surfaces the distinct set for filtering.
    name: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    event: Mapped["Event"] = relationship(back_populates="tags")


class EventPhoto(Base):
    __tablename__ = "event_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Stored on disk under data/uploads/events/<event_id>/<filename>, where
    # filename is "<photo_id><ext>" (mirrors how member photos / job
    # attachments keep binaries out of SQLite). The earliest photo by id
    # acts as the event's cover.
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    event: Mapped["Event"] = relationship(back_populates="photos")
