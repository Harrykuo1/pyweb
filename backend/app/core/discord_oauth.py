"""Discord OAuth2 client for login + guild-membership verification.

Sync httpx calls (mirrors app/core/office_convert.py). Every network
failure degrades to None/False rather than raising, so a Discord outage
yields a clean "login failed" redirect instead of a 500. Tests
monkeypatch httpx.Client.

Flow (driven by the auth router):
  1. build_authorize_url() -> redirect the browser to Discord.
  2. Discord redirects back with ?code=...; exchange_code() -> access token.
  3. fetch_identity() -> the user's snowflake id, username, global_name.
  4. is_guild_member() -> confirm they're still in our guild. Re-checked on
     every login, so leaving the guild revokes access immediately.

Scopes: identify (who they are) + guilds.members.read (membership of a
specific guild via the user's own token -- no bot needed in the guild).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import settings

AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
API_BASE = "https://discord.com/api"
SCOPES = "identify guilds.members.read"

HTTP_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class DiscordIdentity:
    id: str
    username: str
    global_name: str | None


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.discord_client_id,
        "redirect_uri": settings.discord_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "prompt": "consent",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str) -> str | None:
    data = {
        "client_id": settings.discord_client_id,
        "client_secret": settings.discord_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.discord_redirect_uri,
    }
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    try:
        token = resp.json().get("access_token")
    except ValueError:
        return None
    return token if isinstance(token, str) and token else None


def fetch_identity(access_token: str) -> DiscordIdentity | None:
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
            resp = client.get(
                f"{API_BASE}/users/@me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    discord_id = data.get("id")
    username = data.get("username")
    if not isinstance(discord_id, str) or not isinstance(username, str):
        return None
    global_name = data.get("global_name")
    if not isinstance(global_name, str):
        global_name = None
    return DiscordIdentity(id=discord_id, username=username, global_name=global_name)


def is_guild_member(access_token: str, guild_id: str) -> bool:
    if not guild_id:
        return False
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
            resp = client.get(
                f"{API_BASE}/users/@me/guilds/{guild_id}/member",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError:
        return False
    return resp.status_code == 200
