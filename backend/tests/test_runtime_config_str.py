from app.core.runtime_config import DISCORD_GUILD_ID_KEY, get_str
from app.models import AppConfig


def test_get_str_returns_default_when_missing(db_session):
    assert get_str(db_session, DISCORD_GUILD_ID_KEY) == ""
    assert get_str(db_session, "nope", "fallback") == "fallback"


def test_get_str_returns_stored_value(db_session):
    db_session.add(AppConfig(key=DISCORD_GUILD_ID_KEY, value="123456789"))
    db_session.commit()
    assert get_str(db_session, DISCORD_GUILD_ID_KEY) == "123456789"
