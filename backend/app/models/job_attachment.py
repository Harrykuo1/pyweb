from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobAttachment(Base):
    __tablename__ = "job_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # User-facing relative path under data/uploads/jobs/<job_id>/.
    # Single-file uploads put a bare basename here; folder uploads
    # preserve the directory structure with "/" as separator (e.g.
    # "src/components/Foo.vue"). The Content-Disposition header on
    # download uses the same string. Conflict-resolution "rename"
    # bumps the last segment ("report.pdf" -> "report (1).pdf";
    # "src/foo.txt" -> "src/foo (1).txt").
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
