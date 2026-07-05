import pytest

from app.core.security import hash_password, verify_password
from app.models import User, UserRole
from app.reset_password import reset_password


@pytest.fixture
def seeded(db_session):
    db_session.add_all(
        [
            User(
                username="admin",
                password_hash=hash_password("old-pw"),
                role=UserRole.ADMIN,
            ),
            User(
                username="viewer",
                password_hash=hash_password("viewer-pw"),
                role=UserRole.VIEWER,
            ),
        ]
    )
    db_session.commit()
    return db_session


def test_reset_password_updates_hash_and_bumps_version(seeded):
    admin_before = seeded.query(User).filter_by(username="admin").one()
    version_before = admin_before.password_version

    user = reset_password(seeded, "admin", "fresh-pw")

    assert user.username == "admin"
    assert user.password_version == version_before + 1
    assert verify_password("fresh-pw", user.password_hash)
    assert not verify_password("old-pw", user.password_hash)


def test_reset_password_can_target_viewer(seeded):
    user = reset_password(seeded, "viewer", "rotated")
    assert user.role is UserRole.VIEWER
    assert verify_password("rotated", user.password_hash)


def test_reset_password_unknown_user_raises_valueerror(seeded):
    with pytest.raises(ValueError, match="ghost"):
        reset_password(seeded, "ghost", "anything")


def test_reset_password_empty_password_raises_valueerror(seeded):
    with pytest.raises(ValueError, match="empty"):
        reset_password(seeded, "admin", "")


def test_reset_password_persists_through_session(seeded):
    # Verify the commit path: a fresh query in the same session should
    # see the new hash. (Real recovery flow uses SessionLocal in main(),
    # which is exercised below via the CLI test.)
    reset_password(seeded, "admin", "fresh-pw")
    refetched = seeded.query(User).filter_by(username="admin").one()
    assert verify_password("fresh-pw", refetched.password_hash)


# ---------- CLI integration ----------


def test_main_returns_0_and_prints_confirmation(seeded, capsys, monkeypatch):
    # SessionLocal is bound to the production DATABASE_URL via Settings;
    # patch it to hand out the test in-memory session instead.
    from app import reset_password as mod

    class _Ctx:
        def __enter__(self_inner):
            return seeded

        def __exit__(self_inner, *exc):
            return False

    monkeypatch.setattr(mod, "SessionLocal", lambda: _Ctx())

    rc = mod.main(["admin", "cli-pw"])
    assert rc == 0

    out = capsys.readouterr().out
    assert "admin" in out
    assert "password_version" in out

    refetched = seeded.query(User).filter_by(username="admin").one()
    assert verify_password("cli-pw", refetched.password_hash)


def test_main_returns_1_and_prints_error_for_unknown_user(seeded, capsys, monkeypatch):
    from app import reset_password as mod

    class _Ctx:
        def __enter__(self_inner):
            return seeded

        def __exit__(self_inner, *exc):
            return False

    monkeypatch.setattr(mod, "SessionLocal", lambda: _Ctx())

    rc = mod.main(["ghost", "any"])
    assert rc == 1

    err = capsys.readouterr().err
    assert "ghost" in err
