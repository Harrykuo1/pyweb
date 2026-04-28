"""Tests for the alembic-driven schema bring-up.

The full migration story is verified end-to-end in development by
running `alembic upgrade head` against tempdbs (covered manually in
the migration commits). Here we just check that init_db.run_migrations
hands control to alembic with a Config that points at the project's
alembic.ini, and that init_db.main() runs migrations *before* seeding
so the seed never targets a missing schema.
"""
from pathlib import Path
from unittest.mock import patch

from app import init_db


def test_run_migrations_invokes_alembic_with_project_config():
    with patch("app.init_db.command.upgrade") as upgrade:
        init_db.run_migrations()
    assert upgrade.call_count == 1
    cfg, target = upgrade.call_args.args
    # The Config must point at the project's alembic.ini, not whatever
    # cwd alembic is invoked from.
    assert Path(cfg.config_file_name).name == "alembic.ini"
    assert Path(cfg.config_file_name).is_file()
    assert target == "head"


def test_main_runs_migrations_then_seeds(db_session):
    """run_migrations must precede seed_accounts so the seed never hits
    a missing schema. Patch SessionLocal so seeding lands on the
    in-memory test session instead of trying to open the real DB.
    """
    call_order: list[str] = []

    def fake_upgrade(_cfg, _target):
        call_order.append("migrate")

    def fake_seed(db):
        call_order.append("seed")

    class _SessionCtx:
        def __enter__(self):
            return db_session

        def __exit__(self, *_):
            return False

    with patch("app.init_db.command.upgrade", side_effect=fake_upgrade), \
         patch("app.init_db.SessionLocal", return_value=_SessionCtx()), \
         patch("app.init_db.seed_accounts", side_effect=fake_seed):
        init_db.main()

    assert call_order == ["migrate", "seed"]
