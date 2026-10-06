import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Integer,
    LargeBinary,
    String,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.orm import Session

from alembic import command
from app import migrate_sqlite
from app.core.security import hash_password
from app.database import Base, get_db
from app.db_types import UTCDateTime
from app.main import app
from app.models import DatabaseOrigin, MessageEvent, User, UserRole

STAMP = datetime(2026, 1, 2, 10, 30, 4, 123456, tzinfo=UTC)
TOKEN = "imported-bot-token"


@pytest.fixture
def legacy(tmp_path):
    path = tmp_path / "pyweb.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as conn:
        migrate_sqlite.upgrade(conn)
        conn.commit()
    with engine.begin() as conn:
        for table in migrate_sqlite._tables():
            values = {}
            for column in table.columns:
                if column.foreign_keys:
                    values[column.name] = 41
                elif column.nullable:
                    values[column.name] = None
                elif isinstance(column.type, Boolean):
                    values[column.name] = True
                elif isinstance(column.type, Integer):
                    values[column.name] = 41
                elif isinstance(column.type, UTCDateTime):
                    values[column.name] = STAMP
                elif isinstance(column.type, Date):
                    values[column.name] = date(2026, 1, 2)
                elif isinstance(column.type, LargeBinary):
                    values[column.name] = b"\x00\xffpreserve-binary"
                elif isinstance(column.type, String):
                    values[column.name] = "100"
                else:
                    raise AssertionError(column)
                if hasattr(column.type, "enums"):
                    values[column.name] = column.type.enums[0]
            if table.name == "users":
                values.update(
                    username="migrated-admin",
                    password_hash=hash_password("import-pw"),
                    password_version=7,
                    is_active=True,
                )
            if table.name == "jobs":
                values.update(
                    timeline_events=[{"date": "2026-02-03", "event": "中文 😀"}],
                    experience_md="Markdown 中文 😀",
                    is_anonymous=False,
                    status="accepted",
                )
            if table.name == "events":
                values.update(status="accepted")
            if table.name == "activity_ingest_tokens":
                values.update(token_hash=hashlib.sha256(TOKEN.encode()).hexdigest())
            if table.name == "event_videos":
                values.update(kind="youtube", status="ready", youtube_id="abcdefghijk")
            conn.execute(table.insert(), values)
        # Exercise both SQL NULL and JSON null, which SQLAlchemy otherwise
        # deserializes to the same Python value.
        for id_, json_value in [(42, None), (43, JSON.NULL)]:
            jobs = next(t for t in migrate_sqlite._tables() if t.name == "jobs")
            conn.execute(
                jobs.insert(),
                {
                    "id": id_,
                    "job_year": 2026,
                    "job_month": 1,
                    "company": "x",
                    "kind": "internship",
                    "experience_md": "x",
                    "is_anonymous": True,
                    "status": "accepted",
                    "created_at": STAMP,
                    "timeline_events": json_value,
                },
            )
    try:
        yield path, engine
    finally:
        engine.dispose()


@pytest.fixture
def destination(postgres_url):
    engine = create_engine(postgres_url)
    try:
        yield engine
    finally:
        engine.dispose()


def test_import_preserves_every_table_and_redeployment_keeps_new_data(
    legacy, destination
):
    path, source = legacy
    original = path.read_bytes()
    migrate_sqlite.prepare_postgresql(destination, path)
    assert path.read_bytes() == original
    with source.connect() as src, destination.connect() as dst:
        for table in migrate_sqlite._tables():
            assert migrate_sqlite.fingerprint(src, table) == migrate_sqlite.fingerprint(
                dst, table
            ), table.name
        assert dst.execute(
            text(
                "SELECT id, timeline_events IS NULL FROM jobs WHERE id IN (42,43) ORDER BY id"
            )
        ).all() == [(42, True), (43, False)]
    state_path = path.parent / ".postgresql-origin.json"
    record = json.loads(state_path.read_text())
    assert len(record["tables"]) == len(Base.metadata.tables) - 1
    backup = path.parent / "migration-backups" / f"sqlite-{record['identity']}.db"
    assert backup.is_file()
    with Session(destination) as db:
        new_user = User(role=UserRole.MEMBER)
        db.add(new_user)
        db.commit()
        assert new_user.id > 41
        new_id = new_user.id
    migrate_sqlite.prepare_postgresql(destination, path)
    with Session(destination) as db:
        assert db.get(User, new_id) is not None
        assert db.query(DatabaseOrigin).count() == 1
    assert len(list(backup.parent.glob("sqlite-*.db"))) == 1
    assert json.loads(state_path.read_text()) == record


def test_imported_password_session_and_bot_token_keep_working(legacy, destination):
    path, source = legacy
    active = {"engine": source}

    def database():
        with Session(active["engine"]) as db:
            yield db

    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            response = client.post("/api/auth/login", json={"password": "import-pw"})
            assert response.status_code == 200
            assert response.json()["id"] == 41
            endpoints = [
                "/api/members",
                "/api/jobs",
                "/api/events",
                "/api/timeline",
                "/api/stats",
            ]
            before = {endpoint: client.get(endpoint).json() for endpoint in endpoints}
            migrate_sqlite.prepare_postgresql(destination, path)
            active["engine"] = destination
            # Keep the pre-migration cookie: no new login or password reset.
            for endpoint in endpoints:
                response = client.get(endpoint)
                assert response.status_code == 200, (endpoint, response.text)
                assert response.json() == before[endpoint]
            payload = {
                "guild_id": "100",
                "messages": [
                    {
                        "message_id": "999",
                        "user_id": "100",
                        "channel_id": "100",
                        "sent_at": STAMP.isoformat(),
                        "text_length": 12,
                        "attachment_count": 0,
                    }
                ],
            }
            response = client.post(
                "/api/activity/batches",
                json=payload,
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
            assert response.status_code == 200, response.text
            assert response.json()["messages"]["inserted"] == 1
    finally:
        app.dependency_overrides.clear()


def test_snapshot_includes_uncheckpointed_wal(legacy, destination):
    path, _ = legacy
    with sqlite3.connect(path) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("UPDATE users SET username='committed-in-wal'")
        writer.commit()
        assert path.with_name("pyweb.db-wal").stat().st_size > 0
        migrate_sqlite.prepare_postgresql(destination, path)
        with Session(destination) as db:
            assert db.get(User, 41).username == "committed-in-wal"


def test_failure_rolls_back_every_table_and_retry_succeeds(
    legacy, destination, monkeypatch
):
    path, _ = legacy
    real_fingerprint = migrate_sqlite.fingerprint

    def corrupt_comparison(conn, table):
        result = real_fingerprint(conn, table)
        if conn.dialect.name == "postgresql" and table.name == "voice_samples":
            result["sha256"] = "simulated-corruption"
        return result

    monkeypatch.setattr(migrate_sqlite, "fingerprint", corrupt_comparison)
    with pytest.raises(RuntimeError, match="verification failed"):
        migrate_sqlite.prepare_postgresql(destination, path)
    with destination.connect() as conn:
        for table in Base.metadata.sorted_tables:
            assert (
                conn.execute(select(func.count()).select_from(table)).scalar_one() == 0
            )
    assert not (path.parent / ".postgresql-origin.json").exists()
    monkeypatch.setattr(migrate_sqlite, "fingerprint", real_fingerprint)
    migrate_sqlite.prepare_postgresql(destination, path)
    with Session(destination) as db:
        assert db.query(MessageEvent).count() == 1


def test_parallel_initializers_import_only_once(legacy, destination):
    path, _ = legacy
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(
            pool.map(
                lambda _: migrate_sqlite.prepare_postgresql(destination, path), range(2)
            )
        )
    with Session(destination) as db:
        assert db.query(User).count() == 1
        assert db.query(DatabaseOrigin).count() == 1


def test_missing_postgres_volume_refuses_stale_sqlite_reimport(legacy, destination):
    path, _ = legacy
    migrate_sqlite.prepare_postgresql(destination, path)
    with destination.begin() as conn:
        conn.execute(text("DROP TABLE database_origin"))
    with pytest.raises(RuntimeError, match="data is missing"):
        migrate_sqlite.prepare_postgresql(destination, path)


def test_crash_after_commit_before_state_file_is_recoverable(
    legacy, destination, monkeypatch
):
    path, _ = legacy
    write = migrate_sqlite._write_state
    monkeypatch.setattr(
        migrate_sqlite,
        "_write_state",
        lambda *_: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError, match="disk full"):
        migrate_sqlite.prepare_postgresql(destination, path)
    monkeypatch.setattr(migrate_sqlite, "_write_state", write)
    migrate_sqlite.prepare_postgresql(destination, path)
    assert (path.parent / ".postgresql-origin.json").is_file()
    with Session(destination) as db:
        assert db.query(User).count() == 1


def test_older_sqlite_revision_is_upgraded_only_in_working_copy(tmp_path, destination):
    path = tmp_path / "pyweb.db"
    source = create_engine(f"sqlite:///{path}")
    try:
        with source.connect() as conn:
            cfg = Config("alembic.ini")
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "0028")
            conn.execute(
                text(
                    "INSERT INTO events (id, title, event_date, status, created_at) VALUES (99, 'legacy', '2026-01-02', 'accepted', '2026-01-02 00:00:00')"
                )
            )
            conn.commit()
        original = path.read_bytes()
        migrate_sqlite.prepare_postgresql(destination, path)
        assert path.read_bytes() == original
        with destination.connect() as conn:
            assert conn.execute(text("SELECT title, edited_at FROM events")).one() == (
                "legacy",
                None,
            )
    finally:
        source.dispose()


def test_empty_install_and_second_start(tmp_path, destination):
    path = tmp_path / "pyweb.db"
    migrate_sqlite.prepare_postgresql(destination, path)
    migrate_sqlite.prepare_postgresql(destination, path)
    assert not path.exists()
    with Session(destination) as db:
        assert db.query(DatabaseOrigin).one().source is None


def test_populated_unmarked_destination_is_never_overwritten(legacy, destination):
    path, _ = legacy
    with destination.connect() as conn:
        migrate_sqlite.upgrade(conn)
        conn.commit()
    with Session(destination) as db:
        db.add(User(role=UserRole.MEMBER))
        db.commit()
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        migrate_sqlite.prepare_postgresql(destination, path)
    with Session(destination) as db:
        assert db.query(User).count() == 1
        assert db.query(DatabaseOrigin).count() == 0


@pytest.mark.parametrize(
    "problem", ["unknown_table", "foreign_key", "corrupt_file", "missing_revision"]
)
def test_invalid_source_fails_without_creating_origin(legacy, destination, problem):
    path, source = legacy
    if problem == "corrupt_file":
        source.dispose()
        path.write_bytes(b"not a SQLite database")
    else:
        with source.begin() as conn:
            statement = {
                "unknown_table": "CREATE TABLE unknown_legacy_data (id INTEGER)",
                "foreign_key": "UPDATE members SET user_id = 999999",
                "missing_revision": "DROP TABLE alembic_version",
            }[problem]
            conn.execute(text(statement))
    with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
        migrate_sqlite.prepare_postgresql(destination, path)
    with Session(destination) as db:
        assert db.query(DatabaseOrigin).count() == 0
        assert db.query(User).count() == 0


def test_volume_identity_mismatch_stops_startup(legacy, destination):
    path, _ = legacy
    migrate_sqlite.prepare_postgresql(destination, path)
    state = path.parent / ".postgresql-origin.json"
    record = json.loads(state.read_text())
    record["identity"] = "different-volume"
    state.write_text(json.dumps(record))
    with pytest.raises(RuntimeError, match="identity does not match"):
        migrate_sqlite.prepare_postgresql(destination, path)
