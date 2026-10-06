from datetime import UTC, date, datetime

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.db_types import UTCDateTime
from app.models.post_status import PostStatus


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
    # Events are never anonymous; author is the actual creator and drives
    # both display and ownership (edit/delete own).
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    last_edited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    status: Mapped[PostStatus] = mapped_column(
        Enum(
            PostStatus,
            name="event_status",
            values_callable=lambda e: [m.value for m in e],
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=PostStatus.PENDING,
        # Matches migration 0019's ix_events_status (list filters by status).
        index=True,
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    edited_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(timezone=True), nullable=True, index=True
    )

    def mark_edited(self, user_id: int) -> None:
        self.edited_at = datetime.now(UTC)
        self.last_edited_by_user_id = user_id

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
        order_by="EventPhoto.sort_order, EventPhoto.id",
    )
    comments: Mapped[list["EventComment"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventComment.id",
    )
    likes: Mapped[list["EventLike"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )
    videos: Mapped[list["EventVideo"]] = relationship(  # noqa: F821
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventVideo.sort_order, EventVideo.id",
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
    # Position within the event's media, shared with event_videos rather than
    # scoped to photos: the two render as one grid, so ordering only means
    # anything across both. Backfilled from id, so existing events keep the
    # order they already had.
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", index=True
    )
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    event: Mapped["Event"] = relationship(back_populates="photos")


class EventComment(Base):
    __tablename__ = "event_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The commenter. Nullable so a comment survives the author's account
    # deletion (mirrors events.author_user_id); always set on creation.
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    # Plain text (rendered escaped on the client, no Markdown) — comments are
    # short remarks, not posts, so there's no sanitization surface.
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # Stamped when the author edits; drives the "已編輯" marker in the UI.
    edited_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(timezone=True), nullable=True
    )

    event: Mapped["Event"] = relationship(back_populates="comments")


class EventLike(Base):
    __tablename__ = "event_likes"
    __table_args__ = (
        # One like per person per event; the like/unlike endpoints rely on this
        # to stay idempotent.
        UniqueConstraint("event_id", "user_id", name="uq_event_likes_event_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # CASCADE: a like is a join row with no meaning once its user is gone.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    event: Mapped["Event"] = relationship(back_populates="likes")
