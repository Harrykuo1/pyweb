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
