"""Automatic, fail-closed SQLite import during the first PostgreSQL startup.

The deploy script stops all old writers first. The source is never upgraded
or modified: SQLite's backup API includes committed WAL pages, and only a
working copy of that backup receives the historical Alembic migrations.
"""

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path

from alembic.config import Config
from sqlalchemy import (
    JSON,
    Integer,
    MetaData,
    String,
    create_engine,
    func,
    inspect,
    select,
    text,
)

from alembic import command
from app.database import Base
from app.models import DatabaseOrigin

BATCH_SIZE = 2000


def upgrade(connection):
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


def _write_state(path, record):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as tmp:
        try:
            json.dump(record, tmp, sort_keys=True, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            os.replace(tmp.name, path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(tmp.name).unlink(missing_ok=True)


def _snapshot(source, destination):
    # Do not use immutable=1: that silently ignores uncheckpointed WAL data.
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise RuntimeError("SQLite snapshot failed integrity_check")


def _tables():
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name == "database_origin":
            continue
        copied = table.to_metadata(metadata)
        for column in copied.columns:
            if isinstance(column.type, JSON):
                # Preserve SQL NULL separately from the JSON literal null.
                column.type = JSON(none_as_null=True)
    return metadata.sorted_tables


def _rows(connection, table):
    json_columns = [c for c in table.columns if isinstance(c.type, JSON)]
    extras = [c.is_(None).label(f"_null_{c.name}") for c in json_columns]
    order = [
        c.collate("C" if connection.dialect.name == "postgresql" else "BINARY")
        if isinstance(c.type, String)
        else c
        for c in table.primary_key
    ]
    result = connection.execute(
        select(table, *extras).order_by(*order).execution_options(stream_results=True)
    )
    try:
        for partition in result.mappings().partitions(BATCH_SIZE):
            batch = []
            for row in partition:
                values = {c.name: row[c.name] for c in table.columns}
                for column in json_columns:
                    if values[column.name] is None and not row[f"_null_{column.name}"]:
                        values[column.name] = JSON.NULL
                batch.append(values)
            yield batch
    finally:
        result.close()


def _canonical(value):
    if value is JSON.NULL:
        return {"json_literal_null": True}
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=UTC).isoformat()
            if value.tzinfo is None
            else value.astimezone(UTC).isoformat()
        )
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (bytes, memoryview)):
        return {"base64": base64.b64encode(value).decode("ascii")}
    return value


def fingerprint(connection, table):
    digest = hashlib.sha256()
    count = 0
    for batch in _rows(connection, table):
        for row in batch:
            canonical = {key: _canonical(value) for key, value in row.items()}
            digest.update(
                json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()
            )
            digest.update(b"\n")
            count += 1
    return {"rows": count, "sha256": digest.hexdigest()}


def _copy(source, target):
    tables = _tables()
    expected = {t.name for t in tables} | {"alembic_version", "database_origin"}
    actual = set(inspect(source).get_table_names())
    if actual != expected:
        raise RuntimeError(f"Unexpected SQLite tables: {sorted(actual ^ expected)}")
    report = {}
    for table in tables:
        columns = {c["name"] for c in inspect(source).get_columns(table.name)}
        if columns != set(table.columns.keys()):
            raise RuntimeError(f"Unexpected columns in {table.name}")
        if target.execute(select(func.count()).select_from(table)).scalar_one():
            raise RuntimeError(
                f"Refusing to overwrite populated PostgreSQL table: {table.name}"
            )
    if source.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("SQLite snapshot has foreign key violations")
    for table in tables:
        for batch in _rows(source, table):
            target.execute(table.insert(), batch)
        before = fingerprint(source, table)
        after = fingerprint(target, table)
        if before != after:
            raise RuntimeError(f"Import verification failed for {table.name}")
        report[table.name] = after
        # Explicit imported IDs do not advance PostgreSQL sequences.
        if len(table.primary_key) == 1:
            column = next(iter(table.primary_key))
            if isinstance(column.type, Integer) and column.autoincrement is not False:
                sequence = target.execute(
                    text("SELECT pg_get_serial_sequence(:table, :column)"),
                    {"table": table.name, "column": column.name},
                ).scalar_one()
                if sequence:
                    maximum = target.execute(select(func.max(column))).scalar_one()
                    target.execute(
                        text("SELECT setval(:sequence, :value, :called)"),
                        {
                            "sequence": sequence,
                            "value": max(maximum or 1, 1),
                            "called": maximum is not None,
                        },
                    )
    return report


def prepare_postgresql(engine, source_path):
    """Migrate once, or verify the persistent identity on subsequent starts."""
    if engine.dialect.name != "postgresql":
        raise ValueError("The import destination must be PostgreSQL")
    source_path = Path(source_path)
    state_path = source_path.parent / ".postgresql-origin.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else None
    with engine.connect() as connection:
        # Session lock spans Alembic and the import transaction. Parallel
        # startups cannot seed or import over each other.
        connection.execute(
            text(
                "SELECT pg_advisory_lock(hashtext(current_database()), hashtext(current_schema()))"
            )
        )
        connection.commit()
        try:
            if state and "database_origin" not in inspect(connection).get_table_names():
                raise RuntimeError(
                    "PostgreSQL data is missing; refusing to re-import stale SQLite data"
                )
            connection.commit()
            upgrade(connection)
            connection.commit()
            origin = (
                connection.execute(select(DatabaseOrigin.__table__))
                .mappings()
                .one_or_none()
            )
            connection.commit()
            if origin:
                if state and state["identity"] != origin["identity"]:
                    raise RuntimeError(
                        "PostgreSQL volume identity does not match the data directory"
                    )
                record = {
                    "identity": origin["identity"],
                    "source": origin["source"],
                    "tables": origin["tables"],
                }
            else:
                if state:
                    raise RuntimeError(
                        "PostgreSQL import marker is missing; refusing to overwrite data"
                    )
                identity = uuid.uuid4().hex
                backup = None
                report = {}
                # The marker and all imported rows commit together. Any failure
                # leaves an empty, retryable destination and the source intact.
                with connection.begin():
                    if source_path.exists():
                        backup_dir = source_path.parent / "migration-backups"
                        backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                        backup = backup_dir / f"sqlite-{identity}.db"
                        _snapshot(source_path, backup)
                        with tempfile.TemporaryDirectory(dir=backup_dir) as tmp:
                            working = Path(tmp) / "working.db"
                            shutil.copy2(backup, working)
                            sqlite_engine = create_engine(f"sqlite:///{working}")
                            try:
                                with sqlite_engine.connect() as sqlite_connection:
                                    if (
                                        "alembic_version"
                                        not in inspect(
                                            sqlite_connection
                                        ).get_table_names()
                                    ):
                                        raise RuntimeError(
                                            "SQLite source has no Alembic revision; refusing an unverified import"
                                        )
                                    sqlite_connection.commit()
                                    upgrade(sqlite_connection)
                                    sqlite_connection.commit()
                                    report = _copy(sqlite_connection, connection)
                            finally:
                                sqlite_engine.dispose()
                    else:
                        for table in _tables():
                            if connection.execute(
                                select(func.count()).select_from(table)
                            ).scalar_one():
                                raise RuntimeError(
                                    "Unmarked PostgreSQL database is not empty"
                                )
                    record = {
                        "identity": identity,
                        "source": str(backup) if backup else None,
                        "tables": report,
                    }
                    connection.execute(
                        DatabaseOrigin.__table__.insert().values(
                            id=1,
                            completed_at=datetime.now(UTC),
                            **record,
                        )
                    )
            _write_state(state_path, record)
            print(
                f"PostgreSQL ready: {len(record['tables'])} imported tables verified; origin {record['identity']}"
            )
        finally:
            connection.rollback()
            connection.execute(
                text(
                    "SELECT pg_advisory_unlock(hashtext(current_database()), hashtext(current_schema()))"
                )
            )
            connection.commit()
