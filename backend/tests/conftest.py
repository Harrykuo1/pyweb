import os
from contextlib import contextmanager

# Set required env vars before importing app modules so Settings() loads.
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SEED_ADMIN_USERNAME", "test-admin")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "test-admin-pw")
os.environ.setdefault("SEED_VIEWER_USERNAME", "test-viewer")
os.environ.setdefault("SEED_VIEWER_PASSWORD", "test-viewer-pw")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base


@contextmanager
def count_queries(engine):
    """Capture every SQL statement issued against `engine` while the
    block runs. The returned list is appended to in real time, so
    callers can assert exact counts after exiting the block.

    Used to lock in N+1 guarantees on hot list endpoints — if a future
    change accidentally touches a deferred column during list
    serialization, the per-row SELECTs show up here.
    """
    statements: list[str] = []

    def listener(_conn, _cursor, statement, *_args, **_kw):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", listener)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", listener)


@pytest.fixture
def db_engine():
    # In-memory SQLite shared across the same connection (StaticPool) so
    # all sessions in one test see the same data.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Import all model modules so their tables register on Base.metadata.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # The slowapi limiter is module-level singleton state, so a test that
    # runs login() five times will burn through the production budget for
    # every test that follows. Clear the in-memory storage between tests
    # so each one starts with a clean slate. Tests that explicitly want
    # to assert limiter behavior simply make their requests within their
    # own fixture scope.
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def audit_log_dir(tmp_path, monkeypatch):
    """Redirect the audit logger to a per-test temp dir and reset its
    module-level state (file handler + in-memory failure tracker) so the
    suspicious-success counter doesn't leak across tests. Yields the
    directory path so individual tests can read auth.log to assert
    contents."""
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("AUDIT_LOG_DIR", str(log_dir))

    from app.core import audit_log

    audit_log._reset_for_tests()
    yield log_dir
    audit_log._reset_for_tests()
