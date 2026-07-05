"""add photo_path and resume_pdf_path to members and backfill BLOBs to disk

Phase 1 of moving Member photo and resume PDF binaries out of SQLite
BLOB columns and onto the filesystem (mirroring how job attachments
are stored). This revision:

  1. Adds the path columns (``photo_path``, ``resume_pdf_path``)
     relative to ``settings.uploads_dir`` so the data directory can
     be relocated without rewriting rows.
  2. Walks every member with a populated BLOB column, writes the
     bytes to ``uploads_root/members/<id>/`` using the canonical
     filename the production router will read from
     (``photo.<ext>`` per ``photo_content_type`` / ``resume.pdf``),
     stores the relative path, and NULLs the BLOB so 0014's drop
     doesn't have to move data twice.

Photos missing a recognised MIME type are logged and skipped — the
BLOB stays in place and 0014 will refuse to apply against a row that
still carries bytes, surfacing the problem loudly instead of silently
losing data. (resume PDFs are always application/pdf by schema, so
no MIME check is needed.)

The backfill belongs here rather than in a startup hook so every
deployment that runs ``alembic upgrade head`` gets the same one-shot
treatment automatically — including remotes that may still be on
revision 0009 the next time they deploy.

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-23
"""

import logging
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

PHOTO_MIME_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def upgrade() -> None:
    with op.batch_alter_table("members") as batch:
        batch.add_column(sa.Column("photo_path", sa.String(length=512), nullable=True))
        batch.add_column(
            sa.Column("resume_pdf_path", sa.String(length=512), nullable=True)
        )

    # Settings is imported lazily inside upgrade() so ``alembic --autogenerate``
    # or ``alembic upgrade --sql`` (which both load every migration module)
    # don't trip over a missing SESSION_SECRET in environments that aren't
    # actually applying this revision.
    from app.core.config import settings

    uploads_root = Path(settings.uploads_dir)

    conn = op.get_bind()
    members = conn.execute(
        sa.text(
            "SELECT id, photo, photo_content_type, resume_pdf "
            "FROM members "
            "WHERE photo IS NOT NULL OR resume_pdf IS NOT NULL"
        )
    ).fetchall()

    photo_n = pdf_n = skipped = 0
    for mid, photo_bytes, mime, pdf_bytes in members:
        if photo_bytes is not None:
            ext = PHOTO_MIME_TO_EXT.get(mime or "")
            if ext is None:
                logger.warning(
                    "skipping photo backfill for member %s: unknown MIME %r",
                    mid,
                    mime,
                )
                skipped += 1
            else:
                relpath = f"members/{mid}/photo{ext}"
                target = uploads_root / relpath
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(photo_bytes)
                conn.execute(
                    sa.text(
                        "UPDATE members SET photo_path = :p, photo = NULL "
                        "WHERE id = :id"
                    ),
                    {"p": relpath, "id": mid},
                )
                photo_n += 1

        if pdf_bytes is not None:
            relpath = f"members/{mid}/resume.pdf"
            target = uploads_root / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(pdf_bytes)
            conn.execute(
                sa.text(
                    "UPDATE members SET resume_pdf_path = :p, resume_pdf = NULL "
                    "WHERE id = :id"
                ),
                {"p": relpath, "id": mid},
            )
            pdf_n += 1

    if photo_n or pdf_n or skipped:
        logger.info(
            "0013 backfill: %d photos + %d PDFs written to %s (%d skipped)",
            photo_n,
            pdf_n,
            uploads_root,
            skipped,
        )


def downgrade() -> None:
    # The bytes are now on disk; we can't responsibly move them back into
    # the BLOB columns because anything uploaded since 0013 ran would
    # collide with the original payload. Just drop the path columns and
    # leave the on-disk files for the operator to clean up if they want.
    with op.batch_alter_table("members") as batch:
        batch.drop_column("resume_pdf_path")
        batch.drop_column("photo_path")
