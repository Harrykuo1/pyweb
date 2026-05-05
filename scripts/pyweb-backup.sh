#!/usr/bin/env bash
#
# Nightly backup of the SQLite database to a remote configured via rclone.
#
# Strategy: stop the backend container, snapshot the DB, restart, then
# compress and upload. Stopping forces SQLite's last-connection cleanup
# (wal_checkpoint(TRUNCATE) + remove -wal/-shm), so the snapshot is
# guaranteed-consistent — no torn pages, no missed WAL data, no shm
# permission games. Downtime is typically 3–8 seconds.
#
# All knobs are env-vars so this script is safe to commit to a public repo
# without leaking site-specific paths or remote names.
#
# Required env / setup:
#   PYWEB_DATA_DIR    Path to the dir holding pyweb.db. Default: ./data
#   RCLONE_REMOTE     rclone remote + folder. Default: gdrive:pyweb-backups
#   COMPOSE_SERVICE   Service name in docker-compose.yml. Default: backend
#   RETENTION_DAYS    Days of archives to keep. Default: 30
#   COMPOSE_PROJECT_DIR  Working dir for `docker compose`. Default: PWD
#
# Prerequisites on the host:
#   - sqlite3, gzip, rclone, docker (CLI v2 with `compose` subcommand)
#   - The user running this script must be in the `docker` group OR have
#     sudo access for the docker commands; cron user pyparty needs:
#       sudo usermod -aG docker pyparty   (then re-login)
#   - rclone OAuth: ~/.config/rclone/rclone.conf — NEVER commit that file
#
# Cron example:
#     0 3 * * * pyparty cd /home/pyparty/code/pyweb && \
#         RCLONE_REMOTE=pyweb_backup:pyweb-backups \
#         bash scripts/pyweb-backup.sh >> /home/pyparty/pyweb-backup.log 2>&1
#
# Restore (manual): rclone copy the .db.gz, gunzip, stop backend, replace
# data/pyweb.db, restart backend.

set -euo pipefail

PYWEB_DATA_DIR="${PYWEB_DATA_DIR:-./data}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:pyweb-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
COMPOSE_SERVICE="${COMPOSE_SERVICE:-backend}"
COMPOSE_PROJECT_DIR="${COMPOSE_PROJECT_DIR:-$(pwd)}"

DB_PATH="$PYWEB_DATA_DIR/pyweb.db"
if [[ ! -f "$DB_PATH" ]]; then
    echo "ERROR: $DB_PATH not found" >&2
    exit 1
fi

for cmd in sqlite3 gzip rclone docker; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: '$cmd' is not installed" >&2
        exit 1
    fi
done

# Confirm we can talk to docker before doing anything destructive.
if ! docker compose --project-directory "$COMPOSE_PROJECT_DIR" ps >/dev/null 2>&1; then
    echo "ERROR: 'docker compose ps' failed — is the daemon running and is" >&2
    echo "       this user in the 'docker' group? Try: groups" >&2
    exit 1
fi

STAMP=$(date -u +%Y%m%d-%H%M%S)
TMP=$(mktemp -d)
NEEDS_RESTART=false

# Always restart the service if we stopped it, even if the snapshot or
# upload step fails midway. The trap also wipes the host-side tmp dir.
cleanup() {
    local rc=$?
    if [[ "$NEEDS_RESTART" == "true" ]]; then
        docker compose --project-directory "$COMPOSE_PROJECT_DIR" \
            start "$COMPOSE_SERVICE" >/dev/null 2>&1 || true
    fi
    rm -rf "$TMP"
    exit "$rc"
}
trap cleanup EXIT

# Stop the backend so SQLite cleanly closes its last connection. uvicorn
# handles SIGTERM, FastAPI runs lifespan shutdown hooks, SQLAlchemy closes
# the engine, the SQLite WAL gets checkpointed back into the main DB, and
# -wal / -shm are unlinked. -t 30 gives ample time for that chain.
RUNNING=$(docker compose --project-directory "$COMPOSE_PROJECT_DIR" \
    ps --services --filter "status=running" 2>/dev/null || true)
if echo "$RUNNING" | grep -qx "$COMPOSE_SERVICE"; then
    echo "[$STAMP] Stopping $COMPOSE_SERVICE for clean snapshot..."
    docker compose --project-directory "$COMPOSE_PROJECT_DIR" \
        stop -t 30 "$COMPOSE_SERVICE"
    NEEDS_RESTART=true
fi

# At this point the DB is fully at rest; sqlite3 .backup is a true atomic
# snapshot. We add ?immutable=1 for one extra layer of safety: if the
# clean shutdown above left -shm behind for any reason, immutable mode
# skips coordination so we still don't hang on shm permission.
echo "[$STAMP] Snapshotting..."
sqlite3 "file:$DB_PATH?immutable=1" ".backup $TMP/pyweb.db"

# Restart the backend immediately so downtime is bounded by the snapshot
# step alone — gzip and the rclone upload happen with the service back
# online. Toggling NEEDS_RESTART avoids a redundant start in the trap.
if [[ "$NEEDS_RESTART" == "true" ]]; then
    echo "[$STAMP] Restarting $COMPOSE_SERVICE..."
    docker compose --project-directory "$COMPOSE_PROJECT_DIR" \
        start "$COMPOSE_SERVICE"
    NEEDS_RESTART=false
fi

# Verify the snapshot before we ship anything. integrity_check is a full
# B-tree walk; any corruption (torn write that somehow slipped through,
# fs-level damage, etc) shows up here as something other than "ok".
echo "[$STAMP] Verifying integrity..."
result=$(sqlite3 "$TMP/pyweb.db" "PRAGMA integrity_check")
if [[ "$result" != "ok" ]]; then
    echo "ERROR: integrity_check failed: $result" >&2
    exit 1
fi

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
