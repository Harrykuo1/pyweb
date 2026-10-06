from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.db_types import UTCDateTime


class DatabaseOrigin(Base):
    __tablename__ = "database_origin"
    __table_args__ = (CheckConstraint("id = 1", name="ck_database_origin_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    identity: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    tables: Mapped[dict] = mapped_column(JSON, nullable=False)
