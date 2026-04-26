from app.core.security import verify_password
from app.init_db import seed_accounts
from app.models import User, UserRole


def test_seed_accounts_creates_admin_and_viewer(db_session):
    seed_accounts(db_session)

    users = db_session.query(User).order_by(User.username).all()
    assert len(users) == 2

    by_role = {u.role: u for u in users}
    assert UserRole.ADMIN in by_role
    assert UserRole.VIEWER in by_role


def test_seed_accounts_hashes_passwords(db_session):
    from app.core.config import settings

    seed_accounts(db_session)

    admin = db_session.query(User).filter_by(role=UserRole.ADMIN).one()
    # Stored value must not be plaintext, and must verify against the seed.
    assert admin.password_hash != settings.seed_admin_password
    assert verify_password(settings.seed_admin_password, admin.password_hash)


def test_seed_accounts_is_idempotent(db_session):
    seed_accounts(db_session)
    seed_accounts(db_session)
    seed_accounts(db_session)

    assert db_session.query(User).count() == 2


def test_seed_accounts_skips_existing_user_without_overwriting(db_session):
    from app.core.config import settings

    # Pre-create the admin row with a known different hash.
    db_session.add(
        User(
            username=settings.seed_admin_username,
            password_hash="pre-existing-hash",
            role=UserRole.ADMIN,
        )
    )
    db_session.commit()

    seed_accounts(db_session)

    admin = db_session.query(User).filter_by(username=settings.seed_admin_username).one()
    assert admin.password_hash == "pre-existing-hash"
