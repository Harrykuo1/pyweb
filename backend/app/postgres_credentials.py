"""Initialize the Compose bind mount without requiring new operator secrets."""

import os
import secrets
import tempfile
from pathlib import Path


def initialize(data: Path, uid=1000, gid=1000):
    database = data / "postgresql"
    password = data / ".postgres-password"
    if not password.exists() and (database / "PG_VERSION").exists():
        raise RuntimeError(
            "PostgreSQL credential file is missing; restore it from backup"
        )
    database.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.geteuid() == 0:
        os.chown(database, uid, gid)
    if not password.exists():
        with tempfile.NamedTemporaryFile(mode="w", dir=data, delete=False) as tmp:
            try:
                tmp.write(secrets.token_urlsafe(48) + "\n")
                tmp.flush()
                os.fsync(tmp.fileno())
                if os.geteuid() == 0:
                    os.chown(tmp.name, uid, gid)
                try:
                    os.link(tmp.name, password)
                except FileExistsError:
                    pass
            finally:
                Path(tmp.name).unlink(missing_ok=True)
    if not password.read_text().strip():
        raise RuntimeError("PostgreSQL credential file is empty")
    if os.geteuid() == 0:
        os.chown(password, uid, gid)
    password.chmod(0o600)


if __name__ == "__main__":
    initialize(Path("/data"))
