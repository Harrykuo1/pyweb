from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.db_types import UTCDateTime


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 1:1 link to the auth account. Nullable so legacy rows exist before the
    # migration wires them up; a unique index (matching migration 0017's
    # ix_members_user_id) so a user maps to at most one member.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True, unique=True, nullable=True
    )
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=False)
    real_name: Mapped[str] = mapped_column(String(64), nullable=False)
    institution: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # photo_path is relative to settings.uploads_dir (e.g. "members/3/photo.png").
    # The actual bytes live on disk under that path; the router streams
    # them via FileResponse.
    photo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    photo_content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Bumped on every photo upload, cleared on delete. Used by the frontend
    # as a cache-busting version stamp so browsers refetch only when the
    # photo actually changes.
    photo_updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(timezone=True), nullable=True
    )
    resume_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    resume_pdf_updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(timezone=True), nullable=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def has_photo(self) -> bool:
        return self.photo_content_type is not None

    @property
    def has_resume_md(self) -> bool:
        return bool(self.resume_md and self.resume_md.strip())

    @property
    def has_resume_pdf(self) -> bool:
        return self.resume_pdf_updated_at is not None
