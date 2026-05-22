"""Idempotent legacy-layout migration: uploads/<id>/ -> uploads/jobs/<id>/.

The function operates on whatever ``settings.uploads_dir`` points at,
so the test monkeypatches the setting to a tmp dir per case.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.init_db import migrate_uploads_layout


@pytest.fixture
def uploads_root(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "uploads"
    monkeypatch.setattr(settings, "uploads_dir", str(root))
    return root


def test_migrate_moves_numeric_dirs_under_jobs(uploads_root):
    root = uploads_root
    root.mkdir(parents=True)
    (root / "7").mkdir()
    (root / "7" / "deck.pptx").write_bytes(b"x")
    (root / "12").mkdir()
    (root / "12" / "cv.pdf").write_bytes(b"y")

    migrate_uploads_layout()

    assert not (root / "7").exists()
    assert not (root / "12").exists()
    assert (root / "jobs" / "7" / "deck.pptx").read_bytes() == b"x"
    assert (root / "jobs" / "12" / "cv.pdf").read_bytes() == b"y"


def test_migrate_is_idempotent(uploads_root):
    root = uploads_root
    (root / "jobs" / "7").mkdir(parents=True)
    (root / "jobs" / "7" / "deck.pptx").write_bytes(b"x")

    migrate_uploads_layout()
    migrate_uploads_layout()

    assert (root / "jobs" / "7" / "deck.pptx").read_bytes() == b"x"


def test_migrate_skips_non_numeric_dirs(uploads_root):
    root = uploads_root
    root.mkdir()
    (root / "members").mkdir()
    (root / "members" / "photo.png").write_bytes(b"z")

    migrate_uploads_layout()

    # members/ is a sibling category — it must not be swept into jobs/.
    assert (root / "members" / "photo.png").exists()
    assert not (root / "jobs" / "members").exists()


def test_migrate_does_not_clobber_existing_jobs_target(uploads_root):
    """If a same-id dir already exists under jobs/ from a partial
    earlier run, the legacy one is left in place rather than merged.
    The operator can inspect manually."""
    root = uploads_root
    (root / "7").mkdir(parents=True)
    (root / "7" / "old.pptx").write_bytes(b"old")
    (root / "jobs" / "7").mkdir(parents=True)
    (root / "jobs" / "7" / "new.pptx").write_bytes(b"new")

    migrate_uploads_layout()

    assert (root / "7" / "old.pptx").read_bytes() == b"old"
    assert (root / "jobs" / "7" / "new.pptx").read_bytes() == b"new"


def test_migrate_no_op_when_uploads_root_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path / "nope"))
    # Should not raise.
    migrate_uploads_layout()
