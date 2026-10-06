from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# SQLite needs check_same_thread=False because FastAPI runs handlers in
# multiple threads from the same connection pool. For other engines this
# argument is ignored.
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    settings.database_url, connect_args=_connect_args, pool_pre_ping=True
)


def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """SQLAlchemy 'connect' listener — switches the SQLite database into
    WAL mode the first time anyone connects. WAL lets readers run
    concurrently with writers, so an upload no longer blocks the
    members list / photo fetches the way the default rollback journal
    would. The journal_mode setting is persisted in the database file
    so the conversion only happens once. synchronous=NORMAL is the
    WAL-safe sweet spot — full fsync per commit isn't needed.

    busy_timeout makes a connection wait (up to 5s) for a competing writer
    to finish instead of failing instantly with SQLITE_BUSY ("database is
    locked") — WAL still serializes writers, so under concurrent posting
    this is what keeps writes from erroring out.

    Skips :memory: databases — WAL has no meaning without a file."""
    cursor = dbapi_connection.cursor()
    try:
        # PRAGMA database_list tells us the path of the main database.
        # An in-memory database returns an empty file, in which case WAL
        # is silently a no-op.
        rows = cursor.execute("PRAGMA database_list").fetchall()
        path = rows[0][2] if rows else ""
        if path:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


if _is_sqlite:
    event.listen(engine, "connect", _set_sqlite_pragmas)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
