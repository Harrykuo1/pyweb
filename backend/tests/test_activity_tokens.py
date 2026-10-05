import json
from contextlib import nullcontext

import pytest

from app import activity_tokens
from app.activity_tokens import create_token, revoke_token
from app.core.activity_auth import token_digest
from app.models import ActivityIngestToken


def test_credential_only_stores_hash_and_is_revocable(db_session):
    record, secret = create_token(db_session, "100", "collector")
    assert record.token_hash == token_digest(secret)
    assert record.token_hash != secret
    assert record.guild_id == "100"
    assert len(secret) >= 43
    _, second_secret = create_token(db_session, "100", "collector-2")
    assert secret != second_secret
    revoke_token(db_session, record.id)
    first_revocation = record.revoked_at
    revoke_token(db_session, record.id)
    assert record.revoked_at == first_revocation
    assert first_revocation is not None


@pytest.mark.parametrize(
    ("guild_id", "name"),
    [("", "bot"), ("abc", "bot"), ("100", " "), ("100", "x" * 129)],
)
def test_invalid_token_parameters_do_not_persist(db_session, guild_id, name):
    with pytest.raises(ValueError):
        create_token(db_session, guild_id, name)
    assert db_session.query(ActivityIngestToken).count() == 0


def test_cli_create_list_and_revoke(db_session, monkeypatch, capsys):
    monkeypatch.setattr(
        activity_tokens, "SessionLocal", lambda: nullcontext(db_session)
    )
    assert (
        activity_tokens.main(["create", "--guild-id", "100", "--name", "collector"])
        == 0
    )
    created = json.loads(capsys.readouterr().out)
    assert created["guild_id"] == "100"
    assert "token" in created
    assert activity_tokens.main(["list"]) == 0
    listed = capsys.readouterr().out
    assert created["token"] not in listed
    assert "token_hash" not in listed
    assert json.loads(listed)[0]["revoked_at"] is None
    assert activity_tokens.main(["revoke", str(created["id"])]) == 0
    assert db_session.get(ActivityIngestToken, created["id"]).revoked_at is not None
    capsys.readouterr()
    assert activity_tokens.main(["revoke", "999"]) == 1
    assert "not found" in capsys.readouterr().err
