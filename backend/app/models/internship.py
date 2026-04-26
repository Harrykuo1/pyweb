from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Internship(Base):
    __tablename__ = "internships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_year: Mapped[int] = mapped_column(Integer, nullable=False)
    company: Mapped[str] = mapped_column(String(128), nullable=False)
    experience_md: Mapped[str] = mapped_column(Text, nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timeline_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
