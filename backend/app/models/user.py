import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, Enum, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.db_types import UTCDateTime


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    VIEWER = "viewer"
    MEMBER = "member"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Legacy password-login accounts (ADMIN/VIEWER) have a username; Discord
    # accounts do not. Nullable during and after the OAuth migration.
    username: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    # Null for Discord accounts (no password). Still set for legacy accounts
    # until password login is retired.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Bumped whenever the password changes. Stamped into the session at
    # login time and re-checked on every authenticated request, so any
    # session signed before the bump is rejected — that's how we evict
    # other devices when a user (or admin acting on them) rotates the
    # password.
    password_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    # Permanent Discord snowflake — the unique identity key once linked.
    # Nullable while a pre-created member account is waiting for its first
    # OAuth login.
    discord_id: Mapped[str | None] = mapped_column(
        String(32), unique=True, nullable=True, index=True
    )
    # Current @handle at link time. NOT unique: handles are mutable and old
    # ones can be re-registered by someone else; discord_id is the real key.
    discord_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    discord_global_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # One-time migration bridge: the handle parsed from the member's resume
    # at migration time. Matched against the live username on first login,
    # then cleared. Null for new members registered via invite.
    pending_discord_username: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            values_callable=lambda e: [m.value for m in e],
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    # Admin can suspend an account (kick out now, reversibly) without deleting
    # it — the row and its author FKs survive so content and identity persist.
    # Enforced at login and on every authenticated request.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
