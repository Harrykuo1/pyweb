from app.core import runtime_config
from app.core.runtime_config import DISCORD_GUILD_ID_KEY, resolve_guild_id, set_str


def test_resolve_guild_id_prefers_db(db_session, monkeypatch):
    monkeypatch.setattr(runtime_config.settings, "discord_guild_id", "111111111111111111")
    set_str(db_session, DISCORD_GUILD_ID_KEY, "999999999999999999")
    db_session.commit()
    assert resolve_guild_id(db_session) == "999999999999999999"


def test_resolve_guild_id_falls_back_to_env(db_session, monkeypatch):
    monkeypatch.setattr(runtime_config.settings, "discord_guild_id", "111111111111111111")
    assert resolve_guild_id(db_session) == "111111111111111111"


def test_resolve_guild_id_empty_when_neither_set(db_session, monkeypatch):
    monkeypatch.setattr(runtime_config.settings, "discord_guild_id", "")
    assert resolve_guild_id(db_session) == ""
