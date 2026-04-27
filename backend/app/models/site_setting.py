from datetime import datetime, timezone

from sqlalchemy import DateTime, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SiteSetting(Base):
    __tablename__ = "site_settings"

    # Stable string keys (e.g. "login_logo") used directly by the API path,
    # so the table doubles as a typed key/value store for binary assets the
    # admin uploads from the UI.
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
