"""Admin-recovery CLI: rotate a user's password from the host shell.

The web UI's password change endpoint requires an authenticated admin,
which is no help if the only admin has lost their credentials. This
module bypasses the web layer entirely — pointing straight at the DB
through SQLAlchemy — so an operator with shell access on the backend
container can recover.

Usage (from the host):
    docker compose exec backend python -m app.reset_password admin NEW_PW

The command bumps `password_version` alongside the hash so any existing
session for that user is evicted on its next request, matching the
behaviour of the web-UI password change endpoint.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import SessionLocal
from app.models import User


def reset_password(db: Session, username: str, new_password: str) -> User:
    """Rotate `username`'s password to `new_password`.

    Raises ValueError on bad inputs (missing user, blank password) so the
    CLI wrapper can surface a clean stderr message instead of a stack
    trace. Returns the updated User for caller-side logging / assertion.
    """
    if not new_password:
        raise ValueError("New password must not be empty")

    user = db.query(User).filter_by(username=username).one_or_none()
    if user is None:
        raise ValueError(f"User '{username}' not found")

    user.password_hash = hash_password(new_password)
    # Bump the version so any session signed before the reset is
    # rejected on its next request — same eviction guarantee as the
    # web-UI password change.
    user.password_version += 1
    db.commit()
    db.refresh(user)
    return user


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.reset_password",
        description="Reset a user's password from the host shell (admin recovery).",
    )
    parser.add_argument("username", help="The username whose password to rotate.")
    parser.add_argument("new_password", help="The new plaintext password.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        with SessionLocal() as db:
            user = reset_password(db, args.username, args.new_password)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Password reset for user '{user.username}' "
        f"(password_version now {user.password_version})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
