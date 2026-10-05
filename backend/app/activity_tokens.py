"""Operator CLI for guild-scoped, ingestion-only Bot credentials."""

import argparse
import json
import sys
from datetime import UTC, datetime

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.activity_auth import new_token, token_digest
from app.database import SessionLocal
from app.models import ActivityIngestToken
from app.schemas.activity import DiscordId


def create_token(
    db: Session, guild_id: str, name: str
) -> tuple[ActivityIngestToken, str]:
    guild_id = TypeAdapter(DiscordId).validate_python(guild_id)
    name = name.strip()
    if not 1 <= len(name) <= 128:
        raise ValueError("Token name must contain 1–128 characters")
    plain = new_token()
    record = ActivityIngestToken(
        guild_id=guild_id, name=name, token_hash=token_digest(plain)
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, plain


def revoke_token(db: Session, token_id: int) -> None:
    record = db.get(ActivityIngestToken, token_id)
    if record is None:
        raise ValueError("Activity token not found")
    if record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        db.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser(
        "create", help="Create a token; plaintext is shown only once"
    )
    create.add_argument("--guild-id", required=True)
    create.add_argument("--name", required=True)
    commands.add_parser("list", help="List token metadata (never secrets)")
    revoke = commands.add_parser("revoke", help="Immediately revoke a token")
    revoke.add_argument("id", type=int)
    args = parser.parse_args(argv)
    try:
        with SessionLocal() as db:
            if args.command == "create":
                record, plain = create_token(db, args.guild_id, args.name)
                print(
                    json.dumps(
                        {
                            "id": record.id,
                            "guild_id": record.guild_id,
                            "name": record.name,
                            "token": plain,
                        }
                    )
                )
            elif args.command == "revoke":
                revoke_token(db, args.id)
                print(json.dumps({"revoked": args.id}))
            else:
                print(
                    json.dumps(
                        [
                            {
                                "id": t.id,
                                "guild_id": t.guild_id,
                                "name": t.name,
                                "created_at": t.created_at.isoformat(),
                                "revoked_at": t.revoked_at.isoformat()
                                if t.revoked_at
                                else None,
                            }
                            for t in db.query(ActivityIngestToken).order_by(
                                ActivityIngestToken.id
                            )
                        ]
                    )
                )
    except (ValueError, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
