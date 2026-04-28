import tempfile
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text

from app.database import _set_sqlite_pragmas


def test_init_models_creates_users_table(db_engine):
    tables = inspect(db_engine).get_table_names()
    assert "users" in tables


def test_sqlite_pragma_listener_enables_wal_on_file_db():
    # WAL has no effect on :memory: databases (the test fixture uses
    # one), so spin up a tempfile-backed engine just to verify the
    # listener flips the journal mode and tightens fsync.
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "wal-check.db"
        engine = create_engine(f"sqlite:///{db_path}")
        event.listen(engine, "connect", _set_sqlite_pragmas)
        with engine.connect() as conn:
            journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            synchronous = conn.execute(text("PRAGMA synchronous")).scalar()
            foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar()
        engine.dispose()

    assert journal_mode.lower() == "wal"
    # synchronous=NORMAL maps to integer 1 in SQLite.
    assert synchronous == 1
    assert foreign_keys == 1


def test_sqlite_pragma_listener_is_safe_for_memory_db():
    # The listener should NOT try to flip journal_mode on :memory:
    # (WAL is unsupported there) — but the synchronous and
    # foreign_keys lines we still want applied.
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _set_sqlite_pragmas)
    with engine.connect() as conn:
        # No exception means the listener handled :memory: gracefully.
        foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar()
    engine.dispose()
    assert foreign_keys == 1
