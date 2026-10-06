from datetime import UTC, datetime

from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.db_types import UTCDateTime


class SiteSetting(Base):
    __tablename__ = "site_settings"

    # Stable string keys (e.g. "login_logo") used directly by the API path,
    # so the table doubles as a typed key/value store for binary assets the
    # admin uploads from the UI.
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
