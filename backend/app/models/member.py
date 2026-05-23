from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=False)
    real_name: Mapped[str] = mapped_column(String(64), nullable=False)
    institution: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # photo and resume_pdf are deferred so list queries don't drag the
    # multi-MB BLOB through SQLite -> Python memory just to be discarded
    # by the response schema. They get loaded only when the dedicated
    # binary endpoints actually access the column. has_photo and
    # has_resume_pdf below intentionally read the small companion
    # columns (content_type / updated_at) so they don't trigger the
    # deferred load — that's how we avoid turning the optimisation into
    # a real N+1.
    photo: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, deferred=True
    )
    # Path relative to settings.uploads_dir (e.g. "members/3/photo.png").
    # Lives alongside the BLOB column during the migration window; once
    # the startup backfill copies bytes to disk it NULLs the BLOB and
    # the router reads exclusively from photo_path going forward.
    photo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    photo_content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Bumped on every photo upload, cleared on delete. Used by the frontend
    # as a cache-busting version stamp so browsers refetch only when the
    # photo actually changes.
    photo_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # resume_md is intentionally NOT deferred: MemberResponse exposes its
    # raw markdown in the list payload, so deferring would trigger a
    # per-row SELECT during response serialization (i.e. a real N+1).
    resume_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_pdf: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, deferred=True
    )
    resume_pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    resume_pdf_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    @property
    def has_photo(self) -> bool:
        # Read the companion small column rather than the deferred BLOB.
        # photo_content_type is set in lockstep with photo on upload and
        # cleared together on delete, so it's a faithful indicator that
        # doesn't require pulling the bytes off disk.
        return self.photo_content_type is not None

    @property
    def has_resume_md(self) -> bool:
        return bool(self.resume_md and self.resume_md.strip())

    @property
    def has_resume_pdf(self) -> bool:
        # Companion non-deferred column: set on upload, cleared on delete.
        return self.resume_pdf_updated_at is not None
