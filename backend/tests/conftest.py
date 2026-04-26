import os

# Set required env vars before importing app modules so Settings() loads.
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SEED_ADMIN_USERNAME", "test-admin")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "test-admin-pw")
os.environ.setdefault("SEED_VIEWER_USERNAME", "test-viewer")
os.environ.setdefault("SEED_VIEWER_PASSWORD", "test-viewer-pw")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base


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
