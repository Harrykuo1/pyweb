import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone

from pydantic import TypeAdapter
from sqlalchemy import text

from app.main import app
from app.models import User, UserRole


def test_openapi_contract_matches_sqlite_release():
    # Preserve the pre-migration contract while allowing the two new read routes.
    analytics_paths = {"/api/activity/options", "/api/activity/analytics"}
    assert analytics_paths <= app.openapi()["paths"].keys()
    legacy_contract = copy.deepcopy(app.openapi())
    for path in analytics_paths:
        del legacy_contract["paths"][path]
    for schema in {
        "ActivityMetrics",
        "ActivityOptions",
        "ActivityPerson",
        "AnalyticsFilters",
        "AnalyticsResponse",
        "ChannelActivity",
        "DailyActivity",
        "HourlyActivity",
        "MemberActivity",
        "RhythmActivity",
    }:
        del legacy_contract["components"]["schemas"][schema]
    digest = hashlib.sha256(
        json.dumps(legacy_contract, sort_keys=True).encode()
    ).hexdigest()
    assert digest == "fda9008ba1b503cc65f19eac67b4dffe8159fa4d3d3af991bbdd4d385af09881"


def test_timestamp_keeps_utc_instant_and_existing_api_format(db_session):
    stamp = datetime(2026, 1, 2, 18, 30, 4, 123456, tzinfo=timezone(timedelta(hours=8)))
    user = User(role=UserRole.MEMBER, created_at=stamp)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert (
        TypeAdapter(datetime).dump_json(user.created_at)
        == b'"2026-01-02T10:30:04.123456"'
    )
    if db_session.get_bind().dialect.name == "postgresql":
        raw = db_session.execute(text("SELECT created_at FROM users")).scalar_one()
        assert raw == stamp.astimezone(UTC)
        assert raw.tzinfo is not None
