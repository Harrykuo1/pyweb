import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.post_status import PostStatus


class JobKind(str, enum.Enum):
    INTERNSHIP = "internship"
    FULLTIME = "fulltime"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_year: Mapped[int] = mapped_column(Integer, nullable=False)
    job_month: Mapped[int] = mapped_column(Integer, nullable=False)
    company: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    kind: Mapped[JobKind] = mapped_column(
        Enum(
            JobKind,
            name="job_kind",
            values_callable=lambda e: [m.value for m in e],
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    experience_md: Mapped[str] = mapped_column(Text, nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Whose real_name to display ("顯示對象"). New posts point here; legacy
    # rows keep the free-text real_name above as a fallback. Nullable so old
    # rows and admin-picked subjects both work.
    subject_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("members.id"), nullable=True, index=True
    )
    # Who actually created the post ("實際建立者"). Differs from the subject
    # when an admin posts on behalf of a member. Backend keeps this even for
    # anonymous posts; it is never exposed to non-admins.
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    last_edited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    is_anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[PostStatus] = mapped_column(
        Enum(
            PostStatus,
            name="job_status",
            values_callable=lambda e: [m.value for m in e],
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=PostStatus.PENDING,
        # Matches migration 0018's ix_jobs_status (list filters by status).
        index=True,
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Legacy free-form markdown timeline. New jobs write structured
    # entries into timeline_events instead; this column stays for
    # backwards compat — old rows fall through to a deprecated-badge
    # render in the viewer.
    timeline_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured replacement for timeline_md. List of objects shaped
    # like {"month": 2, "day": 23, "event": "投遞履歷"}; the year is
    # implicit (job.job_year) so D+N can be computed honestly even
    # across leap years. Stored as JSON because the row count and
    # columns per entry are short and we never query into them.
    timeline_events: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
