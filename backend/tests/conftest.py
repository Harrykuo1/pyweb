import os
import uuid
from contextlib import contextmanager

# Set required env vars before importing app modules so Settings() loads.
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SEED_ADMIN_USERNAME", "test-admin")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "test-admin-pw")
os.environ.setdefault("SEED_VIEWER_USERNAME", "test-viewer")
os.environ.setdefault("SEED_VIEWER_PASSWORD", "test-viewer-pw")

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
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
def postgres_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set TEST_DATABASE_URL to a disposable PostgreSQL test database")
    schema = "test_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = (
        make_url(url)
        .update_query_dict({"options": f"-csearch_path={schema} -ctimezone=UTC"})
        .render_as_string(hide_password=False)
    )
    try:
        yield isolated
    finally:
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def db_engine(request):
    from app import models  # noqa: F401

    if os.environ.get("TEST_DATABASE_URL"):
        engine = create_engine(request.getfixturevalue("postgres_url"))
        Base.metadata.create_all(bind=engine)
        try:
            yield engine
        finally:
            engine.dispose()
        return
    # In-memory SQLite shared across the same connection (StaticPool) so
    # all sessions in one test see the same data.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Import all model modules so their tables register on Base.metadata.

    # Match production (app/database.py) which enables FK enforcement on
    # every connection, so tests catch FK violations instead of silently
    # ignoring them.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

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
