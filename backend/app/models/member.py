from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=False)
    real_name: Mapped[str] = mapped_column(String(64), nullable=False)
    current_position: Mapped[str] = mapped_column(String(255), nullable=False)
    photo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    photo_content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resume_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_pdf: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    @property
    def has_photo(self) -> bool:
        return self.photo is not None

    @property
    def has_resume_md(self) -> bool:
        return bool(self.resume_md and self.resume_md.strip())

    @property
    def has_resume_pdf(self) -> bool:
        return self.resume_pdf is not None
