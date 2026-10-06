from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.activity_auth import require_activity_token
from app.core.rate_limit import limiter
from app.database import get_db
from app.models import ActivityIngestToken, MessageEvent, VoiceSample
from app.schemas.activity import ActivityBatch, ActivityBatchResponse, IngestCounts

router = APIRouter(prefix="/api/activity", tags=["activity"])


def _insert_records(
    db: Session, model, records: list, guild_id: str, received_at: datetime
) -> IngestCounts:
    if not records:
        return IngestCounts(inserted=0, duplicates=0)
    rows = [
        {**record.model_dump(), "guild_id": guild_id, "received_at": received_at}
        for record in records
    ]
    # Target only the source identity: other constraint violations must roll
    # back the batch rather than being silently discarded by INSERT OR IGNORE.
    statement = insert(model.__table__).on_conflict_do_nothing(
        index_elements=list(model.__table__.primary_key.columns)
    )
    inserted = db.execute(statement, rows).rowcount
    return IngestCounts(inserted=inserted, duplicates=len(rows) - inserted)


@router.post("/batches", response_model=ActivityBatchResponse)
@limiter.limit("60/minute")
def ingest_batch(
    request: Request,
    payload: ActivityBatch,
    token: ActivityIngestToken = Depends(require_activity_token),
    db: Session = Depends(get_db),
) -> ActivityBatchResponse:
    if payload.guild_id != token.guild_id:
        raise HTTPException(status_code=403, detail="Token does not allow this guild")
    received_at = datetime.now(UTC)
    try:
        messages = _insert_records(
            db, MessageEvent, payload.messages, payload.guild_id, received_at
        )
        voice_samples = _insert_records(
            db, VoiceSample, payload.voice_samples, payload.guild_id, received_at
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return ActivityBatchResponse(messages=messages, voice_samples=voice_samples)
