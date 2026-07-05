from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core import discord_oauth
from app.core.config import settings


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "discord_client_id", "cid")
    monkeypatch.setattr(settings, "discord_client_secret", "secret")
    monkeypatch.setattr(
        settings,
        "discord_redirect_uri",
        "http://localhost:8081/api/auth/discord/callback",
    )


class FakeResponse:
    def __init__(self, status_code, *, json_body=None):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, url, *, data=None, headers=None):
        self.calls.append({"method": "POST", "url": url, "data": data})
        return self._response

    def get(self, url, *, headers=None):
        self.calls.append({"method": "GET", "url": url, "headers": headers})
        return self._response


def _patch_client(monkeypatch, response):
    fake = FakeClient(response)
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: fake)
    return fake


# ---------- build_authorize_url ----------


def test_build_authorize_url_carries_params(configured):
    url = discord_oauth.build_authorize_url("st8")
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    assert parsed.netloc == "discord.com"
    assert q["client_id"] == ["cid"]
    assert q["state"] == ["st8"]
    assert q["response_type"] == ["code"]
    assert "identify" in q["scope"][0]
    assert "guilds.members.read" in q["scope"][0]
    assert q["redirect_uri"] == [
        "http://localhost:8081/api/auth/discord/callback"
    ]


# ---------- exchange_code ----------


def test_exchange_code_returns_access_token(configured, monkeypatch):
    _patch_client(monkeypatch, FakeResponse(200, json_body={"access_token": "tok"}))
    assert discord_oauth.exchange_code("abc") == "tok"


def test_exchange_code_none_on_non_200(configured, monkeypatch):
    _patch_client(monkeypatch, FakeResponse(400, json_body={"error": "x"}))
    assert discord_oauth.exchange_code("abc") is None


def test_exchange_code_none_on_network_error(configured, monkeypatch):
    class Boom:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, *a, **k):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "Client", lambda *a, **k: Boom())
    assert discord_oauth.exchange_code("abc") is None


# ---------- fetch_identity ----------


def test_fetch_identity_parses_fields(monkeypatch):
    _patch_client(
        monkeypatch,
        FakeResponse(
            200,
            json_body={"id": "42", "username": "harry", "global_name": "Harry"},
        ),
    )
    ident = discord_oauth.fetch_identity("tok")
    assert ident is not None
    assert ident.id == "42"
    assert ident.username == "harry"
    assert ident.global_name == "Harry"


def test_fetch_identity_none_on_non_200(monkeypatch):
    _patch_client(monkeypatch, FakeResponse(401))
    assert discord_oauth.fetch_identity("tok") is None


def test_fetch_identity_tolerates_missing_global_name(monkeypatch):
    _patch_client(
        monkeypatch,
        FakeResponse(200, json_body={"id": "42", "username": "harry"}),
    )
    ident = discord_oauth.fetch_identity("tok")
    assert ident is not None
    assert ident.global_name is None


# ---------- is_guild_member ----------


def test_is_guild_member_true_on_200(monkeypatch):
    _patch_client(monkeypatch, FakeResponse(200, json_body={"roles": []}))
    assert discord_oauth.is_guild_member("tok", "G1") is True


def test_is_guild_member_false_on_404(monkeypatch):
    _patch_client(monkeypatch, FakeResponse(404))
    assert discord_oauth.is_guild_member("tok", "G1") is False


def test_is_guild_member_false_on_empty_guild_id(monkeypatch):
    called = {"n": 0}

    class Counting:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def get(self, *a, **k):
            called["n"] += 1
            return FakeResponse(200)

    monkeypatch.setattr(httpx, "Client", lambda *a, **k: Counting())
    assert discord_oauth.is_guild_member("tok", "") is False
    assert called["n"] == 0


def test_is_guild_member_false_on_network_error(monkeypatch):
    class Boom:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def get(self, *a, **k):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "Client", lambda *a, **k: Boom())
    assert discord_oauth.is_guild_member("tok", "G1") is False
