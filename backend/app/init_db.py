from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.database import SessionLocal, init_models
from app.models import User, UserRole


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
    init_models()
    with SessionLocal() as db:
        seed_accounts(db)
    print("Database initialized and seeded.")


if __name__ == "__main__":
    main()
