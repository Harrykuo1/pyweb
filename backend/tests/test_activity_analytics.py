from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models import AppConfig, Member, MessageEvent, User, UserRole, VoiceSample


@pytest.fixture
def analytics(db_session):
    admin = User(username="analytics-admin", role=UserRole.ADMIN)
    alice = User(
        discord_id="101", discord_global_name="Alice Discord", role=UserRole.MEMBER
    )
    suspended = User(discord_id="103", role=UserRole.MEMBER, is_active=False)
    db_session.add_all(
        [admin, alice, suspended, AppConfig(key="discord_guild_id", value="999")]
    )
    db_session.flush()
    db_session.add(
        Member(
            user_id=alice.id,
            real_name="Alice",
            graduation_year=2026,
            institution="Test",
        )
    )
    current = [admin]
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: current[0]
    db_session.commit()
    with TestClient(app) as client:
        yield client, current, alice
    app.dependency_overrides.clear()


def message(
    db,
    id_,
    timestamp,
    *,
    user="101",
    channel="201",
    guild="999",
    reply=None,
    length=10,
    attachments=0,
):
    db.add(
        MessageEvent(
            guild_id=guild,
            message_id=str(id_),
            user_id=user,
            channel_id=channel,
            sent_at=datetime.fromisoformat(timestamp),
            reply_to_user_id=reply,
            text_length=length,
            attachment_count=attachments,
        )
    )


def voice(db, timestamp, user="102", guild="999"):
    db.add(
        VoiceSample(
            guild_id=guild,
            user_id=user,
            channel_id="202",
            sampled_at=datetime.fromisoformat(timestamp),
        )
    )


def get(client, **kwargs):
    return client.get(
        "/api/activity/analytics",
        params={"start_date": "2026-10-01", "end_date": "2026-10-05", **kwargs},
    )


def test_requires_session():
    with TestClient(app) as client:
        assert get(client).status_code == 401
        assert client.get("/api/activity/options").status_code == 401


def test_aggregates_raw_events_and_includes_unknown_discord_members(
    analytics, db_session
):
    client, _, _ = analytics
    message(db_session, 1, "2026-09-30T16:00:00+00:00", reply="102", attachments=2)
    message(
        db_session, 2, "2026-10-01T10:00:00+00:00", user="102", channel="203", length=20
    )
    message(db_session, 3, "2026-10-05T15:59:59.999999+00:00")
    message(db_session, 4, "2026-10-05T16:00:00+00:00")
    message(db_session, 5, "2026-09-30T15:59:59+00:00")
    message(db_session, 6, "2026-10-01T12:00:00+00:00", guild="888")
    voice(db_session, "2026-10-01T10:00:23.123456+00:00")
    voice(db_session, "2026-10-01T10:01:23.123456+00:00")
    db_session.commit()
    response = get(client)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["summary"] == {
        "messages": 3,
        "voice_minutes": 2,
        "active_members": 2,
        "active_days": 2,
        "replies": 1,
        "attachments": 2,
        "text_characters": 40,
    }
    assert len(data["daily"]) == 5
    assert data["daily"][0]["messages"] == 2
    assert data["daily"][1]["messages"] == 0
    assert data["hourly"][18]["voice_minutes"] == 2
    assert len(data["rhythm"]) == 168
    for dimension in ["daily", "hourly", "rhythm", "members", "channels"]:
        assert sum(r["messages"] for r in data[dimension]) == 3
        assert sum(r["voice_minutes"] for r in data[dimension]) == 2
    names = {r["user_id"]: r["name"] for r in data["members"]}
    assert names == {"101": "Alice", "102": "Discord · 102"}
    assert data["members"][0]["member_id"] is not None


def test_all_filters_and_exclusive_hour_boundary(analytics, db_session):
    client, _, _ = analytics
    for id_, timestamp in enumerate(
        [
            "2026-10-01T09:59:59+00:00",
            "2026-10-01T10:00:00+00:00",
            "2026-10-01T15:59:59+00:00",
            "2026-10-01T16:00:00+00:00",
            "2026-10-02T10:00:00+00:00",
        ]
    ):
        message(db_session, id_, timestamp)
    message(db_session, 20, "2026-10-01T10:00:00+00:00", user="102")
    message(db_session, 21, "2026-10-01T10:00:00+00:00", channel="202")
    db_session.commit()
    data = get(
        client,
        hour_start=18,
        hour_end=24,
        weekdays=[3],
        user_ids=["101"],
        channel_ids=["201"],
    ).json()
    assert data["summary"]["messages"] == 2
    assert data["daily"][0]["messages"] == 2
    assert get(client, user_ids=["999999"]).json()["summary"]["messages"] == 0


def test_overnight_window_uses_selected_calendar_days(analytics, db_session):
    client, _, _ = analytics
    for id_, hour in enumerate([0, 1, 2, 21, 22, 23]):
        message(db_session, id_, f"2026-10-01T{hour:02}:00:00+00:00")
    db_session.commit()
    data = get(client, timezone="UTC", hour_start=22, hour_end=2).json()
    assert data["summary"]["messages"] == 4
    assert data["hourly"][2]["messages"] == 0


def test_dst_and_local_date_boundaries(analytics, db_session):
    client, _, _ = analytics
    for id_, timestamp in enumerate(
        [
            "2026-11-01T03:59:59+00:00",
            "2026-11-01T04:00:00+00:00",
            "2026-11-01T05:30:00+00:00",
            "2026-11-01T06:30:00+00:00",
            "2026-11-02T04:59:59+00:00",
            "2026-11-02T05:00:00+00:00",
        ]
    ):
        message(db_session, id_, timestamp)
    db_session.commit()
    data = get(
        client,
        start_date="2026-11-01",
        end_date="2026-11-01",
        timezone="America/New_York",
    ).json()
    assert data["summary"]["messages"] == 4
    assert data["hourly"][1]["messages"] == 2


def test_options_and_non_admin_visibility(analytics, db_session):
    client, current, alice = analytics
    message(db_session, 1, "2026-10-01T10:00:00+00:00")
    message(db_session, 2, "2026-10-01T10:00:00+00:00", user="103", channel="205")
    message(
        db_session,
        3,
        "2026-10-01T10:00:00+00:00",
        user="104",
        guild="888",
        channel="206",
    )
    voice(db_session, "2026-10-01T10:00:00+00:00")
    db_session.commit()
    assert get(client).json()["summary"]["messages"] == 2
    current[0] = alice
    data = get(client).json()
    assert data["summary"]["messages"] == 1
    assert {r["user_id"] for r in data["members"]} == {"101", "102"}
    options = client.get("/api/activity/options").json()
    assert options["configured"] is True
    assert {r["user_id"] for r in options["users"]} == {"101", "102"}
    assert options["channels"] == ["201", "202"]
    assert options["last_received_at"] is not None
    assert "205" not in str(options)


def test_incomplete_member_cannot_read_activity(analytics, db_session):
    client, current, _ = analytics
    user = User(role=UserRole.MEMBER, discord_id="105")
    db_session.add(user)
    db_session.commit()
    current[0] = user
    assert get(client).status_code == 403
    assert client.get("/api/activity/options").status_code == 403


@pytest.mark.parametrize(
    "params",
    [
        {"start_date": "bad"},
        {"start_date": "9999-12-31", "end_date": "9999-12-31"},
        {"start_date": "0001-01-01", "end_date": "0001-01-01"},
        {"timezone": "a" * 100},
        {"end_date": "2026-09-30"},
        {"end_date": "2027-10-05"},
        {"timezone": "Not/AZone"},
        {"hour_start": 24},
        {"hour_end": 25},
        {"hour_start": 12, "hour_end": 12},
        {"weekdays": [7]},
        {"weekdays": [-1]},
        {"user_ids": ["1' OR 1=1"]},
        {"channel_ids": ["abc"]},
        {"user_ids": ["1"] * 51},
    ],
)
def test_invalid_queries_are_rejected(analytics, params):
    client, _, _ = analytics
    assert get(client, **params).status_code == 422


def test_empty_and_unconfigured_guild(analytics, db_session, monkeypatch):
    from app.core.config import settings

    client, _, _ = analytics
    assert get(client).json()["summary"]["active_members"] == 0
    options = client.get("/api/activity/options").json()
    assert options["users"] == [] and options["first_record_at"] is None
    db_session.query(AppConfig).delete()
    db_session.commit()
    monkeypatch.setattr(settings, "discord_guild_id", "")
    assert client.get("/api/activity/options").json()["configured"] is False
    data = get(client).json()
    assert len(data["daily"]) == 5 and data["summary"]["messages"] == 0
