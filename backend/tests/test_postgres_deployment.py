import os
import subprocess
import tarfile
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.postgres_credentials import initialize

ROOT = Path(__file__).resolve().parents[2]


def test_credentials_survive_repeated_deployments(tmp_path):
    initialize(tmp_path, os.getuid(), os.getgid())
    path = tmp_path / ".postgres-password"
    first = path.read_text()
    assert len(first.strip()) >= 48
    assert path.stat().st_mode & 0o777 == 0o600
    (tmp_path / "postgresql" / "PG_VERSION").write_text("17")
    initialize(tmp_path, os.getuid(), os.getgid())
    assert path.read_text() == first


def test_lost_credentials_do_not_generate_new_password_for_existing_database(tmp_path):
    database = tmp_path / "postgresql"
    database.mkdir()
    (database / "PG_VERSION").write_text("17")
    with pytest.raises(RuntimeError, match="credential file is missing"):
        initialize(tmp_path)
    assert not (tmp_path / ".postgres-password").exists()


def test_compose_postgres_configuration_overrides_legacy_url_and_escapes_password(
    tmp_path,
):
    path = tmp_path / "password"
    password = "special/@:%?#password"
    path.write_text(password)
    settings = Settings(
        database_url="sqlite:////data/pyweb.db",
        postgres_host="postgres",
        postgres_password_file=str(path),
    )
    url = make_url(settings.database_url)
    assert url.drivername == "postgresql+psycopg"
    assert url.password == password
    assert url.host == "postgres"
    assert url.database == "pyweb"


@pytest.fixture
def fake_docker(tmp_path):
    docker = tmp_path / "docker"
    docker.write_text("""#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
if [[ "$*" == *"${FAIL_COMMAND:-no-match}"* ]]; then exit 1; fi
""")
    docker.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CALLS": str(tmp_path / "calls"),
    }
    return env, tmp_path / "calls"


def test_deployment_stops_old_writers_and_preserves_volumes(fake_docker):
    env, log = fake_docker
    subprocess.run(["bash", str(ROOT / "scripts/deploy.sh")], env=env, check=True)
    calls = log.read_text().splitlines()
    assert calls == [
        "compose build",
        "compose down --remove-orphans",
        "compose up -d --remove-orphans --wait --wait-timeout 900",
        "compose ps",
    ]


def test_failed_build_does_not_stop_existing_site(fake_docker):
    env, log = fake_docker
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh")],
        env={**env, "FAIL_COMMAND": "compose build"},
    )
    assert result.returncode != 0
    assert log.read_text().splitlines() == ["compose build"]


def test_failed_startup_marks_cd_failed_instead_of_reporting_success(fake_docker):
    env, log = fake_docker
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh")],
        env={**env, "FAIL_COMMAND": "compose up"},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "data and SQLite snapshots were retained" in result.stderr
    assert "compose ps" not in log.read_text()


def test_backup_archives_dump_and_files_but_never_live_pgdata(tmp_path):
    data = tmp_path / "data"
    (data / "postgresql").mkdir(parents=True)
    (data / "uploads").mkdir()
    (data / "postgresql" / "live-pages").write_text("must not copy")
    (data / "uploads" / "file").write_bytes(b"uploaded content")
    (data / ".postgres-password").write_text("test credential")
    (data / ".postgresql-origin.json").write_text('{"identity":"test"}')
    (data / "pyweb.db-wal").write_text("must not copy")
    docker = tmp_path / "docker"
    docker.write_text("""#!/usr/bin/env bash
if [[ "$*" == *"pg_dump"* ]]; then printf 'PGDMP-test'; else cat > /dev/null; fi
""")
    docker.chmod(0o755)
    rclone = tmp_path / "rclone"
    rclone.write_text("""#!/usr/bin/env bash
if [[ "$1" == copy ]]; then cp "$2" "$ARCHIVE_DEST"; fi
""")
    rclone.chmod(0o755)
    archive = tmp_path / "backup.tar.gz"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "PYWEB_DATA_DIR": str(data),
        "ARCHIVE_DEST": str(archive),
        "RCLONE_REMOTE": "test-only:",
    }
    subprocess.run(
        ["bash", str(ROOT / "scripts/pyweb-backup.sh")],
        env=env,
        check=True,
        capture_output=True,
    )
    with tarfile.open(archive) as tar:
        names = set(tar.getnames())
        assert "data/postgres.dump" in names
        assert "data/.postgres-password" in names
        assert "data/.postgresql-origin.json" in names
        assert "data/uploads/file" in names
        assert not any("postgresql/" in name or name.endswith("-wal") for name in names)
        assert tar.extractfile("data/postgres.dump").read() == b"PGDMP-test"
