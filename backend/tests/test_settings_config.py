import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import AppConfig, User, UserRole


@pytest.fixture
def client(db_session):
    db_session.add_all([
        User(username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN),
        User(username="viewer", password_hash=hash_password("viewer-pw"), role=UserRole.VIEWER),
    ])
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _login_admin(client):
    assert client.post("/api/auth/login", json={"password": "admin-pw"}).status_code == 200


def _login_viewer(client):
    assert client.post("/api/auth/login", json={"password": "viewer-pw"}).status_code == 200


# ---------- GET ----------


def test_get_config_requires_auth(client):
    r = client.get("/api/settings/config")
    assert r.status_code == 401


def test_get_config_returns_defaults_when_rows_missing(client):
    _login_viewer(client)
    r = client.get("/api/settings/config")
    assert r.status_code == 200
    body = r.json()
    keys = {f["key"]: f for f in body["fields"]}
    assert keys["max_attachments_per_job"]["value"] == 10
    assert keys["max_attachments_per_job"]["type"] == "int"
    assert keys["max_attachments_per_job"]["min"] == 1
    assert keys["max_attachments_per_job"]["max"] == 50
    assert keys["max_attachment_mb"]["value"] == 20


def test_get_config_returns_persisted_values(client, db_session):
    db_session.add(AppConfig(key="max_attachments_per_job", value="15"))
    db_session.commit()

    _login_viewer(client)
    r = client.get("/api/settings/config")
    assert r.status_code == 200
    keys = {f["key"]: f["value"] for f in r.json()["fields"]}
    assert keys["max_attachments_per_job"] == 15
    # Untouched key falls back to its default.
    assert keys["max_attachment_mb"] == 20


# ---------- PUT ----------


def test_put_config_admin_updates_values(client, db_session):
    _login_admin(client)
    r = client.put(
        "/api/settings/config",
        json={"values": {"max_attachments_per_job": 25, "max_attachment_mb": 50}},
    )
    assert r.status_code == 200

    rows = {r.key: r.value for r in db_session.query(AppConfig).all()}
    assert rows["max_attachments_per_job"] == "25"
    assert rows["max_attachment_mb"] == "50"

    # Response reflects the new state.
    keys = {f["key"]: f["value"] for f in r.json()["fields"]}
    assert keys["max_attachments_per_job"] == 25
    assert keys["max_attachment_mb"] == 50


def test_put_config_partial_update_leaves_other_keys_untouched(client, db_session):
    _login_admin(client)
    client.put("/api/settings/config", json={"values": {"max_attachment_mb": 50}})

    keys = {
        r.key: r.value for r in db_session.query(AppConfig).all()
    }
    assert keys.get("max_attachment_mb") == "50"
    # The other field was not in the payload, so no row exists for it
    # and the GET should still report the default.
    assert "max_attachments_per_job" not in keys

    r = client.get("/api/settings/config")
    out = {f["key"]: f["value"] for f in r.json()["fields"]}
    assert out["max_attachments_per_job"] == 10


def test_put_config_viewer_forbidden(client):
    _login_viewer(client)
    r = client.put(
        "/api/settings/config",
        json={"values": {"max_attachments_per_job": 25}},
    )
    assert r.status_code == 403


def test_put_config_unauthenticated(client):
    r = client.put(
        "/api/settings/config",
        json={"values": {"max_attachments_per_job": 25}},
    )
    assert r.status_code == 401


def test_put_config_unknown_key_rejected(client):
    _login_admin(client)
    r = client.put(
        "/api/settings/config",
        json={"values": {"max_attachments_per_job": 25, "bogus_setting": 1}},
    )
    assert r.status_code == 400


def test_put_config_below_min_rejected(client):
    _login_admin(client)
    r = client.put(
        "/api/settings/config",
        json={"values": {"max_attachments_per_job": 0}},
    )
    assert r.status_code == 422


def test_put_config_above_max_rejected(client):
    _login_admin(client)
    r = client.put(
        "/api/settings/config",
        json={"values": {"max_attachments_per_job": 999}},
    )
    assert r.status_code == 422
