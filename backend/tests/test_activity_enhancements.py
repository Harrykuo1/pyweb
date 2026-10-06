import hashlib
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.main import app
from app.models import ActivityChannel, ActivityIngestToken
from tests import test_activity_analytics as fixtures
from tests.test_activity_analytics import get, message, voice

activity_fixture = fixtures.analytics

URL = "/api/activity/channels"
HEADERS = {"Authorization": "Bearer names-test"}


def seed_token(db):
    db.add(
        ActivityIngestToken(
            name="names",
            guild_id="999",
            token_hash=hashlib.sha256(b"names-test").hexdigest(),
        )
    )
    db.commit()


def names(name="聊天大廳", timestamp="2026-01-01T00:00:00Z", **extra):
    return {
        "guild_id": "999",
        "channels": [{"channel_id": "201", "name": name, "observed_at": timestamp}],
        **extra,
    }


def trend(client, **extra):
    return client.get(
        "/api/activity/member-trends",
        params={"end_date": "2026-10-05", "user_ids": ["101", "102"], **extra},
    )


def test_channel_sync_retry_stale_and_guild_isolation(activity_fixture, db_session):
    client, _, _ = activity_fixture
    seed_token(db_session)
    first = client.post(URL, json=names(), headers=HEADERS)
    assert first.status_code == 200, first.text
    assert first.json() == {"updated": 1, "unchanged": 0}
    assert client.post(URL, json=names(), headers=HEADERS).json()["unchanged"] == 1
    assert (
        client.post(
            URL, json=names("新名稱", "2026-01-02T00:00:00Z"), headers=HEADERS
        ).json()["updated"]
        == 1
    )
    assert (
        client.post(URL, json=names("過期名稱"), headers=HEADERS).json()["updated"] == 0
    )
    assert (
        client.post(URL, json=names(guild_id="888"), headers=HEADERS).status_code == 403
    )
    assert db_session.query(ActivityChannel).one().name == "新名稱"
    body = names()
    body["channels"] = [
        names("latest", "2026-01-04T00:00:00Z")["channels"][0],
        names("older", "2026-01-03T00:00:00Z")["channels"][0],
    ]
    assert client.post(URL, json=body, headers=HEADERS).json() == {
        "updated": 1,
        "unchanged": 1,
    }
    db_session.expire_all()
    assert db_session.query(ActivityChannel).one().name == "latest"


def test_names_show_for_historical_data_and_manual_edit_is_admin_only(
    activity_fixture, db_session
):
    client, current, alice = activity_fixture
    message(db_session, 1, "2026-10-01T00:00:00Z")
    db_session.commit()
    assert get(client).json()["channels"][0]["channel_name"] is None
    response = client.patch(f"{URL}/201", json={"name": "  中文頻道 🎉  "})
    assert response.status_code == 200, response.text
    assert get(client).json()["channels"][0]["channel_name"] == "中文頻道 🎉"
    assert client.get("/api/activity/options").json()["channel_names"] == {
        "201": "中文頻道 🎉"
    }
    db_session.add(
        ActivityChannel(
            guild_id="888",
            channel_id="201",
            name="private",
            observed_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
    )
    db_session.commit()
    current[0] = alice
    assert client.patch(f"{URL}/201", json={"name": "bad"}).status_code == 403
    assert get(client).json()["channels"][0]["channel_name"] == "中文頻道 🎉"


@pytest.mark.parametrize("value", ["", " ", "x" * 101, "line\nbreak", 123])
def test_bad_names_are_atomic(activity_fixture, db_session, value):
    client, _, _ = activity_fixture
    seed_token(db_session)
    body = names(value)
    body["channels"].insert(
        0, {"channel_id": "202", "name": "valid", "observed_at": "2026-01-01T00:00:00Z"}
    )
    assert client.post(URL, json=body, headers=HEADERS).status_code == 422
    assert db_session.query(ActivityChannel).count() == 0


def test_sync_token_and_payload_limits(activity_fixture, db_session):
    client, _, _ = activity_fixture
    seed_token(db_session)
    assert client.post(URL, json=names()).status_code == 401
    assert (
        client.post(
            URL, json=names(), headers={"Authorization": "Bearer wrong"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            URL, json=names(timestamp="2026-01-01T00:00:00"), headers=HEADERS
        ).status_code
        == 422
    )
    assert (
        client.post(
            URL, json=names(timestamp="2099-01-01T00:00:00Z"), headers=HEADERS
        ).status_code
        == 422
    )
    assert (
        client.post(
            URL, json=names(channels=names()["channels"] * 1001), headers=HEADERS
        ).status_code
        == 422
    )
    assert (
        client.post(URL, content=b" " * (1024 * 1024 + 1), headers=HEADERS).status_code
        == 413
    )
    token = db_session.query(ActivityIngestToken).one()
    token.revoked_at = datetime.now()
    db_session.commit()
    assert client.post(URL, json=names(), headers=HEADERS).status_code == 401


def test_trends_zero_fill_normalized_rates_and_warmup(activity_fixture, db_session):
    client, _, _ = activity_fixture
    # Current Sep 29–Oct 5; previous Sep 22–28; Sep 21 contributes only to the rolling mean.
    for id_, day in enumerate(
        ["2026-09-21", "2026-09-22", "2026-09-29", "2026-10-05"], 1
    ):
        message(db_session, id_, day + "T10:00:00Z")
    voice(db_session, "2026-10-05T10:00:00Z", user="101")
    db_session.commit()
    response = trend(client, window_days=7)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["current_start"] == "2026-09-29"
    assert data["eligible_current_days"] == data["eligible_previous_days"] == 7
    alice, missing = data["series"]
    assert alice["name"] == "Alice"
    assert len(alice["daily"]) == 14
    assert alice["current_messages"] == 2 and alice["previous_messages"] == 1
    assert alice["current_messages_rate"] == 0.29
    assert alice["messages_change_percent"] == 100
    assert alice["daily"][0]["messages_avg7"] == 0.29
    assert alice["daily"][1]["messages"] == 0
    assert alice["current_voice_minutes"] == 1
    assert alice["voice_minutes_change_percent"] is None
    assert missing["messages_change_percent"] is None
    assert missing["current_messages"] == 0


def test_trends_scope_timezone_overnight_weekday_and_disabled(
    activity_fixture, db_session
):
    client, current, alice = activity_fixture
    for i, kwargs in enumerate(
        [{}, {"guild": "888"}, {"channel": "202"}, {"user": "103"}], 1
    ):
        message(db_session, i, "2026-10-01T16:30:00Z", **kwargs)  # Friday 00:30 Taipei
    message(db_session, 5, "2026-10-02T04:00:00Z")  # noon excluded
    message(db_session, 6, "2026-10-02T16:30:00Z")  # Saturday excluded
    db_session.commit()
    current[0] = alice
    data = trend(
        client,
        user_ids=["101", "103"],
        channel_ids=["201"],
        weekdays=[4],
        hour_start=22,
        hour_end=2,
    ).json()
    assert data["eligible_current_days"] == data["eligible_previous_days"] == 1
    active, disabled = data["series"]
    assert active["current_messages"] == active["current_messages_rate"] == 1
    assert sum(p["messages"] for p in disabled["daily"]) == 0
    assert disabled["member_id"] is None
    assert active["daily"][-4]["date"] == "2026-10-02"
    assert active["daily"][-4]["messages"] == 1


def test_trends_excludes_today_and_future(activity_fixture, db_session, monkeypatch):
    from app.routers import activity_trends

    monkeypatch.setattr(activity_trends, "_local_today", lambda zone: date(2026, 10, 6))
    client, _, _ = activity_fixture
    message(db_session, 1, "2026-10-05T16:00:00Z")  # today Taipei
    db_session.commit()
    for end in ["2026-10-06", "2026-11-01"]:
        data = trend(client, end_date=end).json()
        assert data["excluded_today"] and data["current_end"] == "2026-10-05"
        assert data["series"][0]["current_messages"] == 0


@pytest.mark.parametrize(
    "extra",
    [
        {"window_days": 8},
        {"timezone": "bad"},
        {"user_ids": []},
        {"user_ids": ["1", "2", "3", "4", "5", "6", "7"]},
        {"weekdays": [7]},
        {"hour_start": 5, "hour_end": 5},
        {"user_ids": ["1; DROP TABLE users"]},
        {"end_date": "1960-01-01"},
    ],
)
def test_invalid_trend_filters(activity_fixture, extra):
    assert trend(activity_fixture[0], **extra).status_code == 422


def test_new_routes_require_authentication():
    with TestClient(app) as client:
        assert trend(client).status_code == 401
        assert client.patch(f"{URL}/201", json={"name": "x"}).status_code == 401


def test_channel_migration_preserves_existing_events(postgres_url):
    root = Path(__file__).resolve().parents[1]

    def migrate(operation, revision):
        subprocess.run(
            [sys.executable, "-m", "alembic", operation, revision],
            cwd=root,
            env={**os.environ, "DATABASE_URL": postgres_url},
            check=True,
            capture_output=True,
        )

    migrate("upgrade", "0031")
    engine = create_engine(postgres_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO message_events (guild_id, message_id, user_id, channel_id, sent_at, received_at, text_length, attachment_count) VALUES ('999','1','101','201','2026-01-01','2026-01-01',0,0)"
                )
            )
        for operation, revision in [
            ("upgrade", "0032"),
            ("downgrade", "0031"),
            ("upgrade", "0032"),
        ]:
            migrate(operation, revision)
            assert ("activity_channels" in inspect(engine).get_table_names()) == (
                revision == "0032"
            )
            with engine.connect() as conn:
                assert (
                    conn.execute(
                        text("SELECT message_id FROM message_events")
                    ).scalar_one()
                    == "1"
                )
        assert inspect(engine).get_pk_constraint("activity_channels")[
            "constrained_columns"
        ] == ["guild_id", "channel_id"]
    finally:
        engine.dispose()


def test_30_day_comparison_uses_eligible_weekdays(activity_fixture, db_session):
    client, _, _ = activity_fixture
    # Sep 6–Oct 5 has four Fridays, Aug 7–Sep 5 has five.
    message(db_session, 1, "2026-09-04T10:00:00Z")
    message(db_session, 2, "2026-10-02T10:00:00Z")
    db_session.commit()
    response = trend(client, window_days=30, weekdays=[4])
    assert response.status_code == 200, response.text
    data = response.json()
    assert (data["eligible_current_days"], data["eligible_previous_days"]) == (4, 5)
    person = data["series"][0]
    assert person["current_messages_rate"] == 0.25
    assert person["previous_messages_rate"] == 0.2
    assert person["messages_change_percent"] == 25


def test_dst_repeated_hour_counts_both_instants(
    activity_fixture, db_session, monkeypatch
):
    from app.routers import activity_trends

    monkeypatch.setattr(activity_trends, "_local_today", lambda zone: date(2027, 1, 1))
    client, _, _ = activity_fixture
    for i, stamp in enumerate(
        ["2026-11-01T05:30:00Z", "2026-11-01T06:30:00Z", "2026-11-01T07:00:00Z"], 1
    ):
        message(db_session, i, stamp)
    db_session.commit()
    response = trend(
        client,
        end_date="2026-11-01",
        timezone="America/New_York",
        hour_start=1,
        hour_end=2,
    )
    assert response.status_code == 200, response.text
    data = response.json()["series"][0]
    assert data["daily"][-1]["messages"] == 2
    assert data["current_messages"] == 2


def test_unrelated_identity_is_not_resolved_and_duplicates_are_deduplicated(
    activity_fixture, db_session
):
    client, _, _ = activity_fixture
    message(db_session, 1, "2026-10-01T00:00:00Z", guild="888")
    db_session.commit()
    data = trend(client, user_ids=["101", "101"]).json()
    assert len(data["series"]) == 1
    assert data["series"][0]["name"] == "Discord · 101"
    assert data["series"][0]["member_id"] is None


def test_channel_batch_rolls_back_on_write_failure(
    activity_fixture, db_session, monkeypatch
):
    from app.routers import activity_channels

    client, _, _ = activity_fixture
    seed_token(db_session)
    original = activity_channels._upsert

    def fail_after_write(db, records):
        original(db, records)
        raise RuntimeError("simulated interruption")

    monkeypatch.setattr(activity_channels, "_upsert", fail_after_write)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        client.post(URL, json=names(), headers=HEADERS)
    db_session.rollback()
    assert db_session.query(ActivityChannel).count() == 0
