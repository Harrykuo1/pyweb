from datetime import UTC, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.core.deps import require_completed_member
from app.core.runtime_config import resolve_guild_id
from app.database import get_db
from app.models import Member, User, UserRole
from app.schemas.activity_analytics import (
    ActivityMetrics,
    ActivityOptions,
    ActivityPerson,
    AnalyticsFilters,
    AnalyticsResponse,
    ChannelActivity,
    DailyActivity,
    HourlyActivity,
    MemberActivity,
    RhythmActivity,
)

router = APIRouter(prefix="/api/activity", tags=["activity analytics"])


def _visibility(user: User) -> str:
    if user.role is UserRole.ADMIN:
        return ""
    return "AND NOT EXISTS (SELECT 1 FROM users u WHERE u.discord_id = e.user_id AND NOT u.is_active)"


def _people(db: Session, ids, user: User) -> dict[str, ActivityPerson]:
    result = {id_: ActivityPerson(user_id=id_, name=f"Discord · {id_}") for id_ in ids}
    if not result:
        return result
    query = (
        select(User, Member.id, Member.real_name)
        .outerjoin(Member, Member.user_id == User.id)
        .where(User.discord_id.in_(result))
    )
    if user.role is not UserRole.ADMIN:
        query = query.where(User.is_active.is_(True))
    for account, member_id, name in db.execute(query):
        result[account.discord_id] = ActivityPerson(
            user_id=account.discord_id,
            name=name
            or account.discord_global_name
            or account.discord_username
            or result[account.discord_id].name,
            member_id=member_id,
        )
    return result


@router.get("/options", response_model=ActivityOptions)
def activity_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
):
    guild = resolve_guild_id(db)
    if not guild:
        return ActivityOptions(configured=False, users=[], channels=[])
    visibility = _visibility(current_user)
    rows = (
        db.execute(
            text(f"""
            WITH records AS (
                SELECT user_id, channel_id, sent_at AS happened_at, received_at
                FROM message_events e WHERE guild_id = :guild {visibility}
                UNION ALL
                SELECT user_id, channel_id, sampled_at, received_at
                FROM voice_samples e WHERE guild_id = :guild {visibility}
            )
            SELECT user_id, channel_id, min(happened_at) AS first_at,
                   max(happened_at) AS last_at, max(received_at) AS received_at
            FROM records GROUP BY GROUPING SETS ((), (user_id), (channel_id))
        """),
            {"guild": guild},
        )
        .mappings()
        .all()
    )
    ids = [r["user_id"] for r in rows if r["user_id"] is not None]
    people = _people(db, ids, current_user)
    bounds = next(r for r in rows if r["user_id"] is None and r["channel_id"] is None)
    return ActivityOptions(
        configured=True,
        users=sorted(people.values(), key=lambda p: (p.name, p.user_id)),
        channels=sorted(r["channel_id"] for r in rows if r["channel_id"] is not None),
        first_record_at=bounds["first_at"],
        last_record_at=bounds["last_at"],
        last_received_at=bounds["received_at"],
    )


@router.get("/analytics", response_model=AnalyticsResponse)
def activity_analytics(
    filters: Annotated[AnalyticsFilters, Query()],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
):
    guild = resolve_guild_id(db)
    zone = ZoneInfo(filters.timezone)
    start = datetime.combine(filters.start_date, time.min, zone).astimezone(UTC)
    end = datetime.combine(
        filters.end_date + timedelta(days=1), time.min, zone
    ).astimezone(UTC)
    params = {
        "guild": guild,
        "start": start,
        "end": end,
        "timezone": filters.timezone,
        "hour_start": filters.hour_start,
        "hour_end": filters.hour_end,
    }
    conditions = [_visibility(current_user)]
    expanding = []
    for field, column in [("user_ids", "user_id"), ("channel_ids", "channel_id")]:
        values = getattr(filters, field)
        if values:
            conditions.append(f"AND e.{column} IN :{field}")
            params[field] = values
            expanding.append(bindparam(field, expanding=True))
    where = " ".join(conditions)
    hour_where = (
        "hour >= :hour_start AND hour < :hour_end"
        if filters.hour_start < filters.hour_end
        else "(hour >= :hour_start OR hour < :hour_end)"
    )
    weekday_where = ""
    if filters.weekdays:
        weekday_where = "AND weekday IN :weekdays"
        params["weekdays"] = filters.weekdays
        expanding.append(bindparam("weekdays", expanding=True))
    # Each indexed source range is scanned once. Only grouped results leave SQL.
    query = text(f"""
        WITH records AS (
            SELECT sent_at AS happened_at, user_id, channel_id,
                   1 AS messages, 0 AS voice_minutes,
                   (reply_to_user_id IS NOT NULL)::int AS replies,
                   attachment_count AS attachments, text_length AS text_characters
            FROM message_events e
            WHERE guild_id = :guild AND sent_at >= :start AND sent_at < :end {where}
            UNION ALL
            SELECT sampled_at, user_id, channel_id, 0, 1, 0, 0, 0
            FROM voice_samples e
            WHERE guild_id = :guild AND sampled_at >= :start AND sampled_at < :end {where}
        ), localized AS (
            SELECT *, (happened_at AT TIME ZONE :timezone)::date AS day,
                   EXTRACT(HOUR FROM happened_at AT TIME ZONE :timezone)::int AS hour,
                   EXTRACT(ISODOW FROM happened_at AT TIME ZONE :timezone)::int - 1 AS weekday
            FROM records
        )
        SELECT day, hour, weekday, user_id, channel_id,
               coalesce(sum(messages), 0) AS messages,
               coalesce(sum(voice_minutes), 0) AS voice_minutes,
               count(DISTINCT user_id) AS active_members,
               count(DISTINCT day) AS active_days,
               coalesce(sum(replies), 0) AS replies,
               coalesce(sum(attachments), 0) AS attachments,
               coalesce(sum(text_characters), 0) AS text_characters
        FROM localized WHERE {hour_where} {weekday_where}
        GROUP BY GROUPING SETS ((), (day), (hour), (weekday, hour), (user_id), (channel_id))
    """).bindparams(*expanding)
    rows = db.execute(query, params).mappings().all() if guild else []
    summary = ActivityMetrics()
    daily = {}
    hourly = {}
    rhythm = {}
    members = []
    channels = []
    people = _people(
        db, [r["user_id"] for r in rows if r["user_id"] is not None], current_user
    )
    for row in rows:
        metrics = {key: row[key] for key in ActivityMetrics.model_fields}
        if row["day"] is not None:
            daily[row["day"]] = DailyActivity(date=row["day"], **metrics)
        elif row["weekday"] is not None:
            rhythm[(row["weekday"], row["hour"])] = RhythmActivity(
                weekday=row["weekday"], hour=row["hour"], **metrics
            )
        elif row["hour"] is not None:
            hourly[row["hour"]] = HourlyActivity(hour=row["hour"], **metrics)
        elif row["user_id"] is not None:
            members.append(
                MemberActivity(**people[row["user_id"]].model_dump(), **metrics)
            )
        elif row["channel_id"] is not None:
            channels.append(ChannelActivity(channel_id=row["channel_id"], **metrics))
        else:
            summary = ActivityMetrics(**metrics)
    days = [
        filters.start_date + timedelta(days=i)
        for i in range((filters.end_date - filters.start_date).days + 1)
    ]
    return AnalyticsResponse(
        filters=filters,
        summary=summary,
        daily=[daily.get(day, DailyActivity(date=day)) for day in days],
        hourly=[hourly.get(hour, HourlyActivity(hour=hour)) for hour in range(24)],
        rhythm=[
            rhythm.get((day, hour), RhythmActivity(weekday=day, hour=hour))
            for day in range(7)
            for hour in range(24)
        ],
        members=sorted(
            members, key=lambda m: (-m.messages, -m.voice_minutes, m.user_id)
        ),
        channels=sorted(
            channels, key=lambda c: (-c.messages, -c.voice_minutes, c.channel_id)
        ),
        generated_at=datetime.now(UTC),
    )
