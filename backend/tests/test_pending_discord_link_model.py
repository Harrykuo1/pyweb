from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import PendingDiscordLink


def test_create_pending_link(db_session):
    row = PendingDiscordLink(
        discord_id="555",
        discord_username="ghost",
        discord_global_name="Ghost",
        first_seen_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.commit()
    assert db_session.query(PendingDiscordLink).one().discord_username == "ghost"


def test_pending_link_discord_id_unique(db_session):
    now = datetime.now(UTC)
    db_session.add(PendingDiscordLink(discord_id="555", first_seen_at=now))
    db_session.commit()
    db_session.add(PendingDiscordLink(discord_id="555", first_seen_at=now))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
