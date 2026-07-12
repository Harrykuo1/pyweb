"""Schema definitions for DB-backed runtime config.

These fields live in the `app_configs` table and can be edited by
admins through the settings UI without restarting the server. The
schema here is the single source of truth for: which keys exist,
how their string-encoded values are parsed, what bounds apply, and
which defaults the init_db seeder writes on first boot.

Distinct from `app.core.config.Settings`, which loads immutable
environment variables at process start (secrets, DB URL, etc.).
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.core.config import settings

ConfigType = Literal["int"]


@dataclass(frozen=True)
class ConfigField:
    key: str
    type: ConfigType
    default: str
    min_value: int | None = None
    max_value: int | None = None


CONFIG_FIELDS: tuple[ConfigField, ...] = (
    ConfigField(
        key="max_attachments_per_job",
        type="int",
        default="10",
        min_value=1,
        max_value=50,
    ),
    ConfigField(
        key="max_attachment_mb",
        type="int",
        default="20",
        min_value=1,
        max_value=200,
    ),
)

CONFIG_BY_KEY: dict[str, ConfigField] = {f.key: f for f in CONFIG_FIELDS}


def get_int(db: Session, key: str) -> int:
    """Read an int-typed runtime config value, falling back to the
    seeded default if the row is missing (e.g. a deployment that booted
    before this key was added)."""
    from app.models import AppConfig

    field = CONFIG_BY_KEY[key]
    if field.type != "int":
        raise ValueError(f"Config {key!r} is not an int field")
    row = db.query(AppConfig).filter_by(key=key).one_or_none()
    return int(row.value) if row is not None else int(field.default)


# Admin-editable target Discord guild for OAuth membership checks. Stored
# as a plain string row in app_configs (kept out of the int-only
# CONFIG_FIELDS numeric-config UI); read here, edited via the dedicated
# Discord-settings admin endpoint added in a later phase.
DISCORD_GUILD_ID_KEY = "discord_guild_id"


def get_str(db: Session, key: str, default: str = "") -> str:
    """Read a string-valued runtime config row from app_configs, falling
    back to `default` when the row is missing."""
    from app.models import AppConfig

    row = db.query(AppConfig).filter_by(key=key).one_or_none()
    return row.value if row is not None else default


def resolve_guild_id(db: Session) -> str:
    """The effective guild ID: the DB value if an admin has set one,
    otherwise the env-provided bootstrap default."""
    return get_str(db, DISCORD_GUILD_ID_KEY) or settings.discord_guild_id


def set_str(db: Session, key: str, value: str) -> None:
    """Upsert a string-valued runtime config row. The caller commits."""
    from app.models import AppConfig

    row = db.query(AppConfig).filter_by(key=key).one_or_none()
    if row is None:
        db.add(AppConfig(key=key, value=value))
    else:
        row.value = value
