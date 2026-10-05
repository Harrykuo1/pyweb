import hashlib
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app
from app.models import ActivityIngestToken, MessageEvent, VoiceSample

TOKEN = "test-activity-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
URL = "/api/activity/batches"


def payload():
    return {
        "guild_id": "100",
        "messages": [
            {
                "message_id": "200",
                "user_id": "300",
                "channel_id": "400",
                "sent_at": "2026-01-01T18:00:12.123456+08:00",
                "reply_to_user_id": "500",
                "text_length": 12,
                "attachment_count": 2,
            }
        ],
        "voice_samples": [
            {
                "user_id": "300",
                "channel_id": "400",
                "sampled_at": "2026-01-01T10:00:12.123456Z",
            }
        ],
    }


@pytest.fixture
def client(db_session):
    db_session.add(
        ActivityIngestToken(
            name="test",
            guild_id="100",
            token_hash=hashlib.sha256(TOKEN.encode()).hexdigest(),
        )
    )
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()


def test_batch_persists_metadata_and_exact_utc_time(client, db_session):
    response = client.post(URL, json=payload(), headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "messages": {"inserted": 1, "duplicates": 0},
        "voice_samples": {"inserted": 1, "duplicates": 0},
    }
    msg = db_session.query(MessageEvent).one()
    voice = db_session.query(VoiceSample).one()
    assert msg.sent_at == voice.sampled_at == datetime(2026, 1, 1, 10, 0, 12, 123456)
    assert (
        msg.user_id,
        msg.reply_to_user_id,
        msg.text_length,
        msg.attachment_count,
    ) == ("300", "500", 12, 2)
    assert msg.received_at > msg.sent_at


def test_retry_and_duplicates_within_batch_are_ignored(client, db_session):
    body = payload()
    body["messages"] *= 2
    body["voice_samples"] *= 2
    first = client.post(URL, json=body, headers=HEADERS)
    assert first.status_code == 200, first.text
    assert first.json()["messages"] == {"inserted": 1, "duplicates": 1}
    second = client.post(URL, json=body, headers=HEADERS)
    assert second.json()["messages"] == {"inserted": 0, "duplicates": 2}
    assert second.json()["voice_samples"] == {"inserted": 0, "duplicates": 2}
    assert (
        db_session.query(MessageEvent).count()
        == db_session.query(VoiceSample).count()
        == 1
    )


def test_same_instant_with_different_offset_deduplicates(client):
    assert client.post(URL, json=payload(), headers=HEADERS).status_code == 200
    body = payload()
    body["voice_samples"][0]["sampled_at"] = "2026-01-01T18:00:12.123456+08:00"
    assert (
        client.post(URL, json=body, headers=HEADERS).json()["voice_samples"][
            "duplicates"
        ]
        == 1
    )


def test_different_scan_times_in_same_minute_are_preserved(client, db_session):
    body = payload()
    body["voice_samples"].append(
        {**body["voice_samples"][0], "sampled_at": "2026-01-01T10:00:42Z"}
    )
    assert (
        client.post(URL, json=body, headers=HEADERS).json()["voice_samples"]["inserted"]
        == 2
    )
    assert db_session.query(VoiceSample).count() == 2


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic abc"}]
)
def test_requires_dedicated_bot_token(client, db_session, headers):
    response = client.post(URL, json=payload(), headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert db_session.query(MessageEvent).count() == 0


def test_revoked_token_is_rejected(client, db_session):
    token = db_session.query(ActivityIngestToken).one()
    token.revoked_at = datetime(2026, 1, 1)
    db_session.commit()
    assert client.post(URL, json=payload(), headers=HEADERS).status_code == 401


def test_token_cannot_write_another_guild(client, db_session):
    body = payload()
    body["guild_id"] = "999"
    assert client.post(URL, json=body, headers=HEADERS).status_code == 403
    assert (
        db_session.query(MessageEvent).count()
        == db_session.query(VoiceSample).count()
        == 0
    )


def test_bot_token_does_not_grant_website_access(client):
    assert client.get("/api/members", headers=HEADERS).status_code == 401


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", 300),
        ("message_id", "invalid"),
        ("channel_id", "0"),
        ("sent_at", "2026-01-01T10:00:00"),
        ("sent_at", "2999-01-01T00:00:00Z"),
        ("sent_at", 1700000000),
        ("text_length", -1),
        ("text_length", True),
        ("attachment_count", 1.5),
        ("reply_to_user_id", "invalid"),
        ("content", "do not store"),
    ],
)
def test_invalid_message_rejects_entire_batch(client, db_session, field, value):
    body = payload()
    body["messages"][0][field] = value
    assert client.post(URL, json=body, headers=HEADERS).status_code == 422
    assert (
        db_session.query(MessageEvent).count()
        == db_session.query(VoiceSample).count()
        == 0
    )


def test_invalid_voice_rejects_valid_messages_too(client, db_session):
    body = payload()
    body["voice_samples"][0]["sampled_at"] = "2026-01-01T10:00:00"
    assert client.post(URL, json=body, headers=HEADERS).status_code == 422
    assert db_session.query(MessageEvent).count() == 0


def test_empty_and_oversize_batches_rejected(client):
    assert (
        client.post(URL, json={"guild_id": "100"}, headers=HEADERS).status_code == 422
    )
    body = payload()
    body["messages"] *= 1000
    assert client.post(URL, json=body, headers=HEADERS).status_code == 422


def test_message_only_and_voice_only_batches(client):
    body = payload()
    body.pop("voice_samples")
    assert (
        client.post(URL, json=body, headers=HEADERS).json()["voice_samples"]["inserted"]
        == 0
    )
    body = payload()
    body.pop("messages")
    assert (
        client.post(URL, json=body, headers=HEADERS).json()["messages"]["inserted"] == 0
    )


def test_database_error_rolls_back_both_tables(client, db_engine, db_session):
    def fail_voice(_conn, _cursor, statement, *_args):
        if statement.startswith("INSERT INTO voice_samples"):
            raise OperationalError(statement, {}, Exception("simulated storage error"))

    event.listen(db_engine, "before_cursor_execute", fail_voice)
    try:
        assert client.post(URL, json=payload(), headers=HEADERS).status_code == 500
    finally:
        event.remove(db_engine, "before_cursor_execute", fail_voice)
    assert (
        db_session.query(MessageEvent).count()
        == db_session.query(VoiceSample).count()
        == 0
    )


def test_large_body_is_rejected(client):
    response = client.post(URL, content=b" " * (1024 * 1024 + 1), headers=HEADERS)
    assert response.status_code == 413


def test_rate_limit(client):
    for _ in range(60):
        assert client.post(URL, json=payload(), headers=HEADERS).status_code == 200
    assert client.post(URL, json=payload(), headers=HEADERS).status_code == 429


def test_token_revocation_takes_effect_on_next_request(client, db_session):
    from app.activity_tokens import revoke_token

    assert client.post(URL, json=payload(), headers=HEADERS).status_code == 200
    revoke_token(db_session, db_session.query(ActivityIngestToken).one().id)
    assert client.post(URL, json=payload(), headers=HEADERS).status_code == 401


def test_duplicate_does_not_overwrite_original_metadata(client, db_session):
    assert client.post(URL, json=payload(), headers=HEADERS).status_code == 200
    first_received = db_session.query(MessageEvent).one().received_at
    body = payload()
    body["messages"][0]["text_length"] = 999
    body["voice_samples"][0]["channel_id"] = "999"
    response = client.post(URL, json=body, headers=HEADERS)
    assert response.json()["messages"]["duplicates"] == 1
    assert db_session.query(MessageEvent).one().text_length == 12
    assert db_session.query(MessageEvent).one().received_at == first_received
    assert db_session.query(VoiceSample).one().channel_id == "400"


def test_maximum_batch_of_distinct_events(client, db_session):
    body = payload()
    base = body["messages"][0]
    body["messages"] = [{**base, "message_id": str(1000 + i)} for i in range(999)]
    response = client.post(URL, json=body, headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["messages"]["inserted"] == 999
    assert db_session.query(MessageEvent).count() == 999


def test_oversize_stream_without_content_length(client):
    def chunks():
        for _ in range(17):
            yield b" " * 65536

    response = client.post(URL, content=chunks(), headers=HEADERS)
    assert response.status_code == 413


def test_authenticated_website_admin_still_needs_bot_token(client, db_session):
    from app.core.security import hash_password
    from app.models import User, UserRole

    db_session.add(
        User(
            username="admin",
            password_hash=hash_password("admin-pw"),
            role=UserRole.ADMIN,
        )
    )
    db_session.commit()
    assert (
        client.post("/api/auth/login", json={"password": "admin-pw"}).status_code == 200
    )
    assert client.post(URL, json=payload()).status_code == 401
