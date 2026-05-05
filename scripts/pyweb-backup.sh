#!/usr/bin/env bash
#
# Nightly backup of the SQLite database to a remote configured via rclone.
#
# Designed to run on the host (cron / systemd timer), NOT inside the docker
# container. The container's volume bind-mounts ./data → /data, so the host
# sees the same SQLite file at $PYWEB_DATA_DIR/pyweb.db.
#
# All knobs are env-vars so this script is safe to commit to a public repo
# without leaking site-specific paths or remote names.
#
# Required:
#   PYWEB_DATA_DIR  Path to the dir holding pyweb.db. Default: ./data
#   RCLONE_REMOTE   rclone remote + folder, e.g. "gdrive:pyweb-backups".
#                   Default: gdrive:pyweb-backups
#
# Optional:
#   RETENTION_DAYS  How many days of backups to keep before pruning.
#                   Default: 30
#
# rclone OAuth credentials live in ~/.config/rclone/rclone.conf — this
# script never reads or copies them. NEVER commit that file.
#
# Example cron entry (host crontab):
#     0 3 * * * cd /home/me/pyweb && bash scripts/pyweb-backup.sh \
#         >> /var/log/pyweb-backup.log 2>&1
#
# Restore (manual): pull the .db.gz from your remote, gunzip it, and
# replace data/pyweb.db while the backend container is stopped.

set -euo pipefail

PYWEB_DATA_DIR="${PYWEB_DATA_DIR:-./data}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:pyweb-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

DB_PATH="$PYWEB_DATA_DIR/pyweb.db"
if [[ ! -f "$DB_PATH" ]]; then
    echo "ERROR: $DB_PATH not found" >&2
    exit 1
fi

for cmd in sqlite3 gzip rclone; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: '$cmd' is not installed" >&2
        exit 1
    fi
done

STAMP=$(date -u +%Y%m%d-%H%M%S)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Atomic SQLite snapshot. `.backup` copies pages safely even if the
# backend is mid-write — a plain `cp` could capture a torn file when a
# transaction is in flight.
#
# ?immutable=1 tells SQLite to treat the DB as read-only media and
# bypass the WAL/shm coordination protocol entirely. Without it, an
# unprivileged user (e.g. cron user that doesn't own pyweb.db-shm)
# silently hangs forever — WAL mode requires every connection,
# readers included, to write to the -shm file, and `-readonly` alone
# doesn't waive that requirement.
#
# Trade-off: the snapshot misses any rows still living in pyweb.db-wal
# that haven't been checkpointed back into the main DB yet. SQLite
# auto-checkpoints every ~1000 pages (~4 MB), so for a low-write
# workload the WAL is usually empty at backup time. If you cannot
# accept that gap, schedule a `docker compose stop backend` around
# the backup instead and remove this flag.
sqlite3 "file:$DB_PATH?immutable=1" ".backup $TMP/pyweb.db"

# Compress in place; SQLite is highly compressible (lots of NULL padding,
# repetitive BLOB headers), typically 3–5× smaller after gzip -9.
gzip -9 "$TMP/pyweb.db"
ARCHIVE="$TMP/pyweb-$STAMP.db.gz"
mv "$TMP/pyweb.db.gz" "$ARCHIVE"

echo "[$STAMP] Uploading $(du -h "$ARCHIVE" | cut -f1) → $RCLONE_REMOTE/"
rclone copy "$ARCHIVE" "$RCLONE_REMOTE/"

# Prune old archives. --min-age means "objects with mtime older than X".
echo "[$STAMP] Pruning archives older than ${RETENTION_DAYS}d"
rclone delete --min-age "${RETENTION_DAYS}d" "$RCLONE_REMOTE/"

echo "[$STAMP] Backup complete"
