from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.activity_auth import require_activity_token
from app.core.deps import require_admin
from app.core.rate_limit import limiter
from app.core.runtime_config import resolve_guild_id
from app.database import get_db
from app.models import ActivityChannel, ActivityIngestToken, User
from app.schemas.activity_channels import (
    ChannelNameResponse,
    ChannelNamesBatch,
    ChannelNamesResult,
    ChannelNameUpdate,
)

router = APIRouter(prefix="/api/activity/channels", tags=["activity channels"])


def _upsert(db, records):
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(ActivityChannel).values(records)
    statement = statement.on_conflict_do_update(
        index_elements=["guild_id", "channel_id"],
        set_={
            key: getattr(statement.excluded, key)
            for key in ["name", "observed_at", "updated_at"]
        },
        where=statement.excluded.observed_at > ActivityChannel.observed_at,
    )
    return len(db.execute(statement.returning(ActivityChannel.channel_id)).all())


@router.post("", response_model=ChannelNamesResult)
@limiter.limit("60/minute")
def sync_channel_names(
    request: Request,
    payload: ChannelNamesBatch,
    token: ActivityIngestToken = Depends(require_activity_token),
    db: Session = Depends(get_db),
):
    if payload.guild_id != token.guild_id:
        raise HTTPException(status_code=403, detail="Token does not allow this guild")
    latest = {}
    for record in payload.channels:
        if (
            record.channel_id not in latest
            or record.observed_at > latest[record.channel_id].observed_at
        ):
            latest[record.channel_id] = record
    now = datetime.now(UTC)
    records = [
        {**record.model_dump(), "guild_id": payload.guild_id, "updated_at": now}
        for _, record in sorted(latest.items())
    ]
    updated = _upsert(db, records)
    db.commit()
    return ChannelNamesResult(
        updated=updated, unchanged=len(payload.channels) - updated
    )


@router.patch("/{channel_id}", response_model=ChannelNameResponse)
def edit_channel_name(
    channel_id: Annotated[str, Path(pattern=r"^[1-9][0-9]{0,19}$")],
    payload: ChannelNameUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    guild = resolve_guild_id(db)
    if not guild:
        raise HTTPException(status_code=422, detail="請先設定 Discord 群組")
    now = datetime.now(UTC)
    # Manual edits take effect immediately, even if a bot's clock is slightly ahead.
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(ActivityChannel).values(
        guild_id=guild,
        channel_id=channel_id,
        name=payload.name,
        observed_at=now,
        updated_at=now,
    )
    db.execute(
        statement.on_conflict_do_update(
            index_elements=["guild_id", "channel_id"],
            set_={"name": payload.name, "observed_at": now, "updated_at": now},
        )
    )
    db.commit()
    return ChannelNameResponse(channel_id=channel_id, name=payload.name, updated_at=now)
