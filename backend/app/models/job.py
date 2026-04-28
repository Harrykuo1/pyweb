import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobKind(str, enum.Enum):
    INTERNSHIP = "internship"
    FULLTIME = "fulltime"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_year: Mapped[int] = mapped_column(Integer, nullable=False)
    company: Mapped[str] = mapped_column(String(128), nullable=False)
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
    timeline_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
