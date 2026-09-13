import enum
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VideoKind(str, enum.Enum):
    """Where the bytes live.

    An uploaded video is transcoded and served from our own disk; a YouTube
    one is a reference and costs no storage. They share a table because they
    share everything the event page cares about — ordering, captions, the
    per-event count — and differ only in how they play.
    """

    UPLOAD = "upload"
    YOUTUBE = "youtube"


class VideoStatus(str, enum.Enum):
    """Transcoding progress. YouTube rows are READY from the start."""

    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class EventVideo(Base):
    __tablename__ = "event_videos"
    __table_args__ = (
        # The users table taught this lesson: it holds two identities in one
        # row with every column nullable and the rule that a Discord account
        # never has a password living only in a comment — which is exactly
        # how it drifted. Here the rule is in the schema instead.
        CheckConstraint(
            "(kind = 'youtube' AND filename IS NULL"
            " AND youtube_id IS NOT NULL AND length(youtube_id) = 11)"
            " OR (kind = 'upload' AND youtube_id IS NULL)",
            name="ck_event_videos_kind_shape",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[VideoKind] = mapped_column(
        Enum(
            VideoKind,
            name="event_video_kind",
            values_callable=lambda e: [m.value for m in e],
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[VideoStatus] = mapped_column(
        Enum(
            VideoStatus,
            name="event_video_status",
            values_callable=lambda e: [m.value for m in e],
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # ---- kind=upload ----
    # The transcoded H.264/AAC MP4 under data/uploads/events/<event_id>/.
    # Null while transcoding and after a failure — there is nothing to serve.
    # The original is not kept: it is HEVC nobody can play, and keeping it
    # would triple what the nightly backup tarball carries.
    filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # A frame pulled from the video, so the media grid has a tile to show
    # instead of a black rectangle.
    poster_filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ---- kind=youtube ----
    # The 11-character id, never the URL the user pasted. Storing the id
    # shrinks what reaches an iframe from arbitrary text to a fixed-charset
    # token, and the embed URL is rebuilt rather than echoed.
    youtube_id: Mapped[str | None] = mapped_column(String(11), nullable=True)

    # ---- transcode bookkeeping ----
    # Set when transcoding begins. A container restart mid-transcode would
    # otherwise strand the row in PROCESSING forever, with the event page
    # spinning on a video that will never arrive; startup sweeps anything
    # older than the timeout into FAILED and deletes its files.
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Failed rows stay visible so the uploader learns to retry rather than
    # watching their upload silently vanish, then age out on a later sweep.
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # ffmpeg's reason. Shown to admins only — it names paths and codecs.
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped["Event"] = relationship(back_populates="videos")  # noqa: F821
