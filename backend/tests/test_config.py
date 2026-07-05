from app.core.config import settings


def test_discord_oauth_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "discord_client_id", "")
    monkeypatch.setattr(settings, "discord_client_secret", "")
    monkeypatch.setattr(settings, "discord_redirect_uri", "")
    assert settings.discord_oauth_configured is False


def test_discord_oauth_enabled_when_all_three_set(monkeypatch):
    monkeypatch.setattr(settings, "discord_client_id", "cid")
    monkeypatch.setattr(settings, "discord_client_secret", "secret")
    monkeypatch.setattr(settings, "discord_redirect_uri", "http://x/cb")
    assert settings.discord_oauth_configured is True


def test_discord_oauth_partial_config_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "discord_client_id", "cid")
    monkeypatch.setattr(settings, "discord_client_secret", "")
    monkeypatch.setattr(settings, "discord_redirect_uri", "http://x/cb")
    assert settings.discord_oauth_configured is False
