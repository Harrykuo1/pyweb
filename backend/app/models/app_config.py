from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppConfig(Base):
    __tablename__ = "app_configs"

    # Values are stored as text and decoded against the typed schema in
    # app.core.runtime_config at the API boundary; the table itself is
    # type-agnostic so adding a new config knob is a row insert, not a
    # schema migration.
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
