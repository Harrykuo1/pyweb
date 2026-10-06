from datetime import UTC, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.deps import require_completed_member
from app.core.runtime_config import resolve_guild_id
from app.database import get_db
from app.models import User
from app.routers.activity_analytics import _people, _visibility
from app.schemas.activity_analytics import ActivityPerson
from app.schemas.activity_trends import (
    MemberTrendFilters,
    MemberTrendPoint,
    MemberTrendSeries,
    MemberTrendsResponse,
)

router = APIRouter(prefix="/api/activity", tags=["activity analytics"])


def _local_today(zone):
    return datetime.now(zone).date()


def _change(current, previous):
    return round((current - previous) / previous * 100, 1) if previous else None


@router.get("/member-trends", response_model=MemberTrendsResponse)
def member_trends(
    filters: Annotated[MemberTrendFilters, Query()],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_completed_member),
):
    zone = ZoneInfo(filters.timezone)
    today = _local_today(zone)
    end = min(filters.end_date, today - timedelta(days=1))
    start = end - timedelta(days=filters.window_days - 1)
    previous_end = start - timedelta(days=1)
    previous_start = start - timedelta(days=filters.window_days)
    warmup_start = previous_start - timedelta(days=6)
    guild = resolve_guild_id(db)
    params = {
        "guild": guild,
        "user_ids": filters.user_ids,
        "start": datetime.combine(warmup_start, time.min, zone).astimezone(UTC),
        "end": datetime.combine(end + timedelta(days=1), time.min, zone).astimezone(
            UTC
        ),
        "timezone": filters.timezone,
        "hour_start": filters.hour_start,
        "hour_end": filters.hour_end,
    }
    visibility = _visibility(current_user)
    channel_where = ""
    binds = [bindparam("user_ids", expanding=True)]
    if filters.channel_ids:
        channel_where = "AND channel_id IN :channel_ids"
        params["channel_ids"] = filters.channel_ids
        binds.append(bindparam("channel_ids", expanding=True))
    weekday_where = ""
    if filters.weekdays:
        weekday_where = "AND weekday IN :weekdays"
        params["weekdays"] = filters.weekdays
        binds.append(bindparam("weekdays", expanding=True))
    hour_where = (
        "hour >= :hour_start AND hour < :hour_end"
        if filters.hour_start < filters.hour_end
        else "(hour >= :hour_start OR hour < :hour_end)"
    )
    query = text(f"""
        WITH records AS (
            SELECT user_id, sent_at AS happened_at, 1 AS messages, 0 AS voice_minutes
            FROM message_events e WHERE guild_id = :guild AND user_id IN :user_ids
                AND sent_at >= :start AND sent_at < :end {visibility} {channel_where}
            UNION ALL
            SELECT user_id, sampled_at, 0, 1 FROM voice_samples e
            WHERE guild_id = :guild AND user_id IN :user_ids
                AND sampled_at >= :start AND sampled_at < :end {visibility} {channel_where}
        ), localized AS (
            SELECT *, (happened_at AT TIME ZONE :timezone)::date AS day,
                EXTRACT(HOUR FROM happened_at AT TIME ZONE :timezone)::int AS hour,
                EXTRACT(ISODOW FROM happened_at AT TIME ZONE :timezone)::int - 1 AS weekday
            FROM records
        )
        SELECT user_id, day, sum(messages) AS messages, sum(voice_minutes) AS voice_minutes
        FROM localized WHERE {hour_where} {weekday_where} GROUP BY user_id, day
    """).bindparams(*binds)
    rows = db.execute(query, params).mappings().all() if guild else []
    # Resolve names only for identities recorded in this guild, even outside this window.
    identity_query = text(f"""
        SELECT user_id FROM message_events e WHERE guild_id = :guild AND user_id IN :user_ids {visibility}
        UNION
        SELECT user_id FROM voice_samples e WHERE guild_id = :guild AND user_id IN :user_ids {visibility}
    """).bindparams(bindparam("user_ids", expanding=True))
    ids = (
        db.execute(identity_query, {"guild": guild, "user_ids": filters.user_ids})
        .scalars()
        .all()
        if guild
        else []
    )
    people = _people(db, ids, current_user)
    counts = {
        (r["user_id"], r["day"]): (int(r["messages"]), int(r["voice_minutes"]))
        for r in rows
    }
    dates = [previous_start + timedelta(days=i) for i in range(filters.window_days * 2)]

    def eligible(day):
        return not filters.weekdays or day.weekday() in filters.weekdays

    current_days = sum(eligible(d) for d in dates if d >= start)
    previous_days = sum(eligible(d) for d in dates if d < start)
    series = []
    for id_ in filters.user_ids:
        person = people.get(id_, ActivityPerson(user_id=id_, name=f"Discord · {id_}"))
        points = []
        for day in dates:
            window = [day - timedelta(days=i) for i in range(7)]
            denominator = sum(eligible(d) for d in window)
            values = counts.get((id_, day), (0, 0))
            averages = [
                sum(counts.get((id_, d), (0, 0))[i] for d in window) / denominator
                if denominator
                else 0
                for i in [0, 1]
            ]
            points.append(
                MemberTrendPoint(
                    date=day,
                    messages=values[0],
                    voice_minutes=values[1],
                    messages_avg7=round(averages[0], 2),
                    voice_minutes_avg7=round(averages[1], 2),
                )
            )
        current = [p for p in points if p.date >= start]
        previous = [p for p in points if p.date < start]
        message_count = sum(p.messages for p in current)
        old_message_count = sum(p.messages for p in previous)
        voice_count = sum(p.voice_minutes for p in current)
        old_voice_count = sum(p.voice_minutes for p in previous)
        message_rate = message_count / current_days if current_days else 0
        old_message_rate = old_message_count / previous_days if previous_days else 0
        voice_rate = voice_count / current_days if current_days else 0
        old_voice_rate = old_voice_count / previous_days if previous_days else 0
        series.append(
            MemberTrendSeries(
                **person.model_dump(),
                daily=points,
                current_messages=message_count,
                previous_messages=old_message_count,
                current_voice_minutes=voice_count,
                previous_voice_minutes=old_voice_count,
                current_messages_rate=round(message_rate, 2),
                previous_messages_rate=round(old_message_rate, 2),
                current_voice_minutes_rate=round(voice_rate, 2),
                previous_voice_minutes_rate=round(old_voice_rate, 2),
                messages_change_percent=_change(message_rate, old_message_rate),
                voice_minutes_change_percent=_change(voice_rate, old_voice_rate),
            )
        )
    return MemberTrendsResponse(
        timezone=filters.timezone,
        window_days=filters.window_days,
        current_start=start,
        current_end=end,
        previous_start=previous_start,
        previous_end=previous_end,
        eligible_current_days=current_days,
        eligible_previous_days=previous_days,
        excluded_today=filters.end_date >= today,
        series=series,
        generated_at=datetime.now(UTC),
    )
