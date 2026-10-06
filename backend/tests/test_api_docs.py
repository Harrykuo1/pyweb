import json

from app.models import User, UserRole
from app.schemas.activity import ActivityBatch
from app.schemas.activity_channels import ChannelNamesBatch
from tests import test_settings_router as fixtures

client = fixtures.client
URL = "/api/admin/api-docs"


def test_documentation_requires_admin_session(client, db_session):
    assert client.get(URL).status_code == 401
    assert (
        client.get(URL, headers={"Authorization": "Bearer example"}).status_code == 401
    )
    fixtures._login_viewer(client)
    assert client.get(URL).status_code == 403
    client.cookies.clear()
    fixtures._login_admin(client)
    response = client.get(URL)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    admin = db_session.query(User).filter_by(username="admin").one()
    admin.role = UserRole.MEMBER
    db_session.commit()
    assert client.get(URL).status_code == 403
    admin.is_active = False
    db_session.commit()
    assert client.get(URL).status_code == 401


def test_reference_tracks_live_schema_without_modifying_global_schema(client):
    from app.main import app

    fixtures._login_admin(client)
    before = json.dumps(app.openapi(), sort_keys=True)
    body = client.get(URL).json()
    assert body["openapi"]["paths"] == {
        path: item
        for path, item in app.openapi()["paths"].items()
        if path.startswith("/api/")
    }
    assert body["openapi"]["components"] == app.openapi()["components"]
    assert "/api/activity/batches" in body["openapi"]["paths"]
    assert all(not path.startswith("/internal/") for path in body["openapi"]["paths"])
    assert json.dumps(app.openapi(), sort_keys=True) == before
    for key, note in body["guide"]["endpoint_notes"].items():
        method, path = key.split(" ", 1)
        assert method.lower() in body["openapi"]["paths"][path]
        assert note["auth"] and note["description"]


def test_guide_payloads_match_runtime_validation_and_token_commands(client):
    fixtures._login_admin(client)
    sections = {
        section["id"]: section
        for section in client.get(URL).json()["guide"]["sections"]
    }
    batch = json.loads(sections["batches"]["snippets"][0]["code"])
    channels = json.loads(sections["channels"]["snippets"][0]["code"])
    assert ActivityBatch.model_validate(batch).guild_id == channels["guild_id"]
    assert ChannelNamesBatch.model_validate(channels).channels[0].name
    commands = "\n".join(snippet["code"] for snippet in sections["tokens"]["snippets"])
    for command in [
        "docker compose exec backend python -m app.activity_tokens create",
        "docker exec -it pyweb-backend-1 python -m app.activity_tokens create",
        "--guild-id",
        "--name",
        "app.activity_tokens list",
        "app.activity_tokens revoke 1",
    ]:
        assert command in commands
    assert "沒有自動到期日" in sections["tokens"]["body"]
    # Samples must be placeholders, never database-backed token metadata.
    assert "token_hash" not in json.dumps(sections)
