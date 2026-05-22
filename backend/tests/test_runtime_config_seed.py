from app.core.runtime_config import CONFIG_FIELDS
from app.init_db import seed_runtime_config
from app.models import AppConfig


def test_seed_runtime_config_writes_default_rows(db_session):
    seed_runtime_config(db_session)

    rows = {r.key: r.value for r in db_session.query(AppConfig).all()}
    for field in CONFIG_FIELDS:
        assert rows.get(field.key) == field.default


def test_seed_runtime_config_preserves_admin_overrides(db_session):
    # First boot writes defaults.
    seed_runtime_config(db_session)

    # Admin changes a value through the settings UI (simulated as a direct
    # write). Re-running the seeder on a later restart must not clobber it.
    db_session.query(AppConfig).filter_by(key="max_attachments_per_job").update(
        {"value": "25"}
    )
    db_session.commit()

    seed_runtime_config(db_session)

    row = db_session.query(AppConfig).filter_by(key="max_attachments_per_job").one()
    assert row.value == "25"
