from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import User, UserRole

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def run_migrations() -> None:
    """Bring the database schema up to head via Alembic.

    On a fresh DB this runs every revision starting from the baseline.
    On a deployment that predates Alembic, the operator must run
    `alembic stamp 0001` once out-of-band so this call only applies the
    post-baseline migrations instead of trying to recreate tables that
    already exist.
    """
    cfg = Config(str(ALEMBIC_INI))
    command.upgrade(cfg, "head")


def _upsert_seed_user(db: Session, username: str, password: str, role: UserRole) -> None:
    existing = db.query(User).filter_by(username=username).one_or_none()
    if existing is not None:
        return
    db.add(
        User(
            username=username,
            password_hash=hash_password(password),
            role=role,
        )
    )


def seed_accounts(db: Session) -> None:
    _upsert_seed_user(
        db,
        settings.seed_admin_username,
        settings.seed_admin_password,
        UserRole.ADMIN,
    )
    _upsert_seed_user(
        db,
        settings.seed_viewer_username,
        settings.seed_viewer_password,
        UserRole.VIEWER,
    )
    db.commit()


def main() -> None:
    run_migrations()
    with SessionLocal() as db:
        seed_accounts(db)
    print("Database initialized and seeded.")


if __name__ == "__main__":
    main()
