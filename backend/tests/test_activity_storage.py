from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.core.config import settings
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


def test_migration_roundtrip_keeps_existing_data(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "0029")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO events (title, event_date, status, created_at) VALUES ('keep', '2026-10-05', 'accepted', '2026-10-05 10:00:00')"
            )
        )
    try:
        for operation, revision in [
            (command.upgrade, "0030"),
            (command.downgrade, "0029"),
            (command.upgrade, "0030"),
        ]:
            operation(config, revision)
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
    finally:
        engine.dispose()
