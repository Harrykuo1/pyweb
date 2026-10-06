import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.models import MessageEvent, VoiceSample

STAMP = datetime(2026, 10, 5, 10, 0, 12, 123456, tzinfo=UTC)


def test_raw_data_preserves_external_ids_and_exact_scan_time(db_session):
    db_session.add(
        MessageEvent(
            guild_id="100",
            message_id="200",
            user_id="300",
            channel_id="400",
            sent_at=STAMP,
            reply_to_user_id="500",
            text_length=12,
            attachment_count=2,
        )
    )
    db_session.add(
        VoiceSample(guild_id="100", user_id="300", channel_id="400", sampled_at=STAMP)
    )
    db_session.commit()
    msg = db_session.query(MessageEvent).one()
    voice = db_session.query(VoiceSample).one()
    assert (msg.reply_to_user_id, msg.text_length, msg.attachment_count) == (
        "500",
        12,
        2,
    )
    assert voice.sampled_at == STAMP.replace(tzinfo=None)
    assert msg.received_at is not None and voice.received_at is not None
    assert not hasattr(voice, "minute_bucket")


@pytest.mark.parametrize("model", [MessageEvent, VoiceSample])
def test_database_rejects_duplicate_source_events(db_session, model):
    fields = {"guild_id": "100", "user_id": "300", "channel_id": "400"}
    fields.update(
        {"message_id": "200", "sent_at": STAMP, "text_length": 0, "attachment_count": 0}
        if model is MessageEvent
        else {"sampled_at": STAMP}
    )
    db_session.add(model(**fields))
    db_session.commit()
    db_session.add(model(**fields))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert db_session.query(model).count() == 1


def test_migration_roundtrip_keeps_existing_data(tmp_path):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    root = Path(__file__).resolve().parents[1]
    logger = logging.getLogger(__name__)
    was_disabled = logger.disabled

    def migrate(operation, revision):
        # Alembic's fileConfig disables unrelated loggers; keep its global
        # logging setup out of the pytest worker and subsequent tests.
        subprocess.run(
            [sys.executable, "-m", "alembic", operation, revision],
            cwd=root,
            env={**os.environ, "DATABASE_URL": url},
            check=True,
            capture_output=True,
        )

    migrate("upgrade", "0029")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO events (title, event_date, status, created_at) VALUES ('keep', '2026-10-05', 'accepted', '2026-10-05 10:00:00')"
            )
        )
    try:
        for operation, revision in [
            ("upgrade", "0030"),
            ("downgrade", "0029"),
            ("upgrade", "0030"),
        ]:
            migrate(operation, revision)
            inspector = inspect(engine)
            assert ("message_events" in inspector.get_table_names()) == (
                revision == "0030"
            )
            with engine.connect() as conn:
                assert (
                    conn.execute(text("SELECT title FROM events")).scalar_one()
                    == "keep"
                )
                assert conn.execute(text("PRAGMA foreign_key_check")).all() == []
        assert {
            tuple(i["column_names"])
            for i in inspect(engine).get_indexes("message_events")
        } == {
            ("guild_id", "sent_at"),
            ("guild_id", "user_id", "sent_at"),
            ("guild_id", "channel_id", "sent_at"),
        }
        assert logger.disabled == was_disabled
    finally:
        engine.dispose()
