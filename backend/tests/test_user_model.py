import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models import User, UserRole


def test_create_user_with_admin_role(db_session):
    user = User(username="admin", password_hash="hash1", role=UserRole.ADMIN)
    db_session.add(user)
    db_session.commit()

    fetched = db_session.query(User).filter_by(username="admin").one()
    assert fetched.role is UserRole.ADMIN
    assert fetched.created_at is not None


def test_create_user_with_viewer_role(db_session):
    user = User(username="viewer", password_hash="hash2", role=UserRole.VIEWER)
    db_session.add(user)
    db_session.commit()

    fetched = db_session.query(User).filter_by(username="viewer").one()
    assert fetched.role is UserRole.VIEWER


def test_username_must_be_unique(db_session):
    db_session.add(User(username="dup", password_hash="h", role=UserRole.VIEWER))
    db_session.commit()

    db_session.add(User(username="dup", password_hash="h2", role=UserRole.VIEWER))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_role_rejects_invalid_value(db_session):
    # Bypass the Python enum and try to write a raw invalid string.
    user = User(username="bad", password_hash="h", role="superuser")
    db_session.add(user)
    with pytest.raises(SQLAlchemyError):
        db_session.commit()
    db_session.rollback()
