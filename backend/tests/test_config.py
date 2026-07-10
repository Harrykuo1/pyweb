from app.core.config import Settings, settings


def test_settings_session_secure_defaults_false():
    s = Settings(
        session_secret="x",
        seed_admin_username="a",
        seed_admin_password="a",
        seed_viewer_username="v",
        seed_viewer_password="v",
    )
    assert s.session_secure is False


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
