import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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
