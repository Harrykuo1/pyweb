from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic.config import Config
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import settings
from app.core.event_media import video_files
from app.core.runtime_config import CONFIG_FIELDS
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import AppConfig, EventVideo, User, UserRole, VideoStatus

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def run_migrations() -> None:
    """Bring the database schema up to head via Alembic.

    On a fresh DB this runs every revision starting from the baseline.
    On a deployment that predates Alembic, the operator must run
    `alembic stamp 0001` once out-of-band so this call only applies the
    post-baseline migrations instead of trying to recreate tables that
    already exist.
    """
    cfg = Config(str(ALEMBIC_INI))
    command.upgrade(cfg, "head")


def _upsert_seed_user(
    db: Session, username: str, password: str, role: UserRole
) -> None:
    # Probe by role, not username. The seed represents the initial slot
    # for that role; once any user of the role exists we've moved past
    # initialization. Looking up by the original username would treat a
    # renamed seed account ("viewer" → "PY!") as missing and insert a
    # duplicate viewer on the next container restart.
    existing = db.query(User).filter_by(role=role).first()
    if existing is not None:
        return
    db.add(
        User(
            username=username,
            password_hash=hash_password(password),
            role=role,
        )
    )


def seed_accounts(db: Session) -> None:
    _upsert_seed_user(
        db,
        settings.seed_admin_username,
        settings.seed_admin_password,
        UserRole.ADMIN,
    )
    _upsert_seed_user(
        db,
        settings.seed_viewer_username,
        settings.seed_viewer_password,
        UserRole.VIEWER,
    )
    db.commit()


def _upsert_seed_config(db: Session, key: str, value: str) -> None:
    existing = db.query(AppConfig).filter_by(key=key).one_or_none()
    if existing is not None:
        return
    db.add(AppConfig(key=key, value=value))


def seed_runtime_config(db: Session) -> None:
    for field in CONFIG_FIELDS:
        _upsert_seed_config(db, field.key, field.default)
    db.commit()


def migrate_uploads_layout() -> None:
    """Move legacy ``uploads/<job_id>/`` directories into the new
    ``uploads/jobs/<job_id>/`` subtree.

    Earlier versions parked every job's attachments directly under
    uploads_root, which would collide with future upload types
    (members/, projects/, ...) trying to share the same numeric-id
    namespace. The nested layout reserves the top level for
    category buckets.

    Idempotent: subsequent runs see no numeric-named dir at the top
    and quietly exit. Existing on-disk targets in jobs/ are left
    untouched on purpose so a half-completed run doesn't clobber a
    newly-uploaded file.
    """
    uploads_root = Path(settings.uploads_dir)
    if not uploads_root.exists():
        return
    jobs_root = uploads_root / "jobs"
    for child in uploads_root.iterdir():
        if not child.is_dir():
            continue
        if not child.name.isdigit():
            continue
        jobs_root.mkdir(parents=True, exist_ok=True)
        target = jobs_root / child.name
        if target.exists():
            continue
        child.rename(target)


# How long a failed video stays visible before it is cleared out. Long enough
# that whoever uploaded it comes back, sees why, and retries.
FAILED_VIDEO_RETENTION_DAYS = 7


def sweep_interrupted_videos(db: Session, uploads_root: Path) -> None:
    """Resolve videos left mid-transcode by a restart, and retire old failures.

    Transcoding runs in-process, so nothing survives the container stopping.
    That means every PROCESSING row seen at startup is orphaned by definition
    — no elapsed-time threshold needed, because the process that owned it is
    gone. Left alone they would spin on the event page forever.

    Their files go immediately: a half-written MP4 plus the original upload is
    up to several hundred megabytes of nothing, and the nightly backup would
    carry it. The row stays, marked FAILED, because an upload that silently
    vanishes leaves the uploader unable to tell whether it ever happened.
    """
    now = datetime.now(UTC)

    stranded = db.query(EventVideo).filter_by(status=VideoStatus.PROCESSING).all()
    for video in stranded:
        for path in video_files(video, uploads_root):
            path.unlink(missing_ok=True)
        video.filename = None
        video.poster_filename = None
        video.status = VideoStatus.FAILED
        video.failed_at = now
        video.error_detail = "轉檔在伺服器重新啟動時中斷，請重新上傳"

    cutoff = now - timedelta(days=FAILED_VIDEO_RETENTION_DAYS)
    expired = (
        db.query(EventVideo)
        .filter(
            EventVideo.status == VideoStatus.FAILED,
            EventVideo.failed_at.isnot(None),
            EventVideo.failed_at < cutoff,
        )
        .all()
    )
    for video in expired:
        for path in video_files(video, uploads_root):
            path.unlink(missing_ok=True)
        db.delete(video)

    if stranded or expired:
        db.commit()
        print(
            f"Videos: {len(stranded)} interrupted transcode(s) marked failed, "
            f"{len(expired)} stale failure(s) removed."
        )


def main() -> None:
    run_migrations()
    migrate_uploads_layout()
    with SessionLocal() as db:
        seed_accounts(db)
        seed_runtime_config(db)
        sweep_interrupted_videos(db, Path(settings.uploads_dir))
    print("Database initialized and seeded.")


if __name__ == "__main__":
    main()
