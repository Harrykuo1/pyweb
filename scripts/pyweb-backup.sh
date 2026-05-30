#!/usr/bin/env bash
#
# Hot snapshot of the entire data/ directory to a remote configured via
# rclone. Designed to run on the host (cron / systemd timer) without
# stopping the backend container.
#
# Strategy
# --------
#   1. sqlite3 .backup ?immutable=1   →  tmp/pyweb.db   (atomic DB snapshot)
#   2. cp -a $PYWEB_DATA_DIR/. tmp/data/                (everything else)
#   3. Replace tmp/data/pyweb.db with the snapshot from step 1
#   4. Remove transient SQLite coordination files (-wal, -shm) from tmp/data
#   5. tar czf the whole tmp/data
#   6. rclone copy + prune
#
# Why copy the whole directory instead of listing uploads/ + logs/
# explicitly? So when we add new subdirectories under data/ later
# (data/exports/, data/cache/, whatever) they get backed up automatically
# without anyone having to remember to update this script.
#
# Trade-offs (hot, no stop):
#   * The DB snapshot via ?immutable=1 skips the wal-index protocol so it
#     works regardless of shm permission, but misses rows still in
#     pyweb.db-wal that haven't been auto-checkpointed. SQLite checkpoints
#     every ~1000 pages (~4 MB); for a low-write workload the WAL is
#     usually empty.
#   * cp -a races with in-flight uploads at a window of tens of ms per
#     file. The backend writes attachments with Path.write_bytes(), which
#     is not atomic. For a community site updated every few days at 3 am
#     local, the probability of hitting it is effectively zero.
#
# Required env / setup:
#   PYWEB_DATA_DIR    Path to the bind-mounted data dir. Default: ./data
#   RCLONE_REMOTE     rclone remote + folder. Default: gdrive:pyweb-backups
#   RETENTION_DAYS    Days of archives to keep. Default: 30
#
# Prerequisites on the host:
#   - sqlite3, tar, gzip, rclone
#   - rclone OAuth: ~/.config/rclone/rclone.conf — NEVER commit that file
#
# Cron example (run as the user that owns ~/.config/rclone/rclone.conf —
# do NOT use sudo or run from root's crontab, that would silently rewrite
# data/* ownership and break the running container's writes):
#     0 3 * * * cd /home/me/pyweb && \
#         RCLONE_REMOTE=pyweb_backup:pyweb-backups \
#         bash scripts/pyweb-backup.sh >> /home/me/pyweb-backup.log 2>&1
#
# Restore (manual):
#     rclone copy gdrive:pyweb-backups/pyweb-STAMP.tar.gz .
#     docker compose stop backend
#     rm -rf data
#     tar xzf pyweb-STAMP.tar.gz
#     docker compose start backend

set -euo pipefail

PYWEB_DATA_DIR="${PYWEB_DATA_DIR:-./data}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:pyweb-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

DB_PATH="$PYWEB_DATA_DIR/pyweb.db"
if [[ ! -f "$DB_PATH" ]]; then
    echo "ERROR: $DB_PATH not found" >&2
    exit 1
fi
if [[ ! -d "$PYWEB_DATA_DIR" ]]; then
    echo "ERROR: $PYWEB_DATA_DIR is not a directory" >&2
    exit 1
fi

for cmd in sqlite3 tar gzip rclone; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: '$cmd' is not installed" >&2
        exit 1
    fi
done

# Refuse to run as root: cron-as-root would rewrite data/* ownership and
# break the container's ability to write back into the same files.
if [[ $EUID -eq 0 ]]; then
    echo "ERROR: do not run this script as root." >&2
    echo "       Use a non-root user's crontab (the same user that owns" >&2
    echo "       ~/.config/rclone/rclone.conf)." >&2
    exit 1
fi

STAMP=$(date -u +%Y%m%d-%H%M%S)
TMP=$(mktemp -d)
STAGE="$TMP/data"
trap 'rm -rf "$TMP"' EXIT

# 1. Atomic DB snapshot first. ?immutable=1 lets us read regardless of
#    shm permission and skips lock coordination; trade-off documented
#    at the top of this file.
echo "[$STAMP] Snapshotting pyweb.db..."
sqlite3 "file:$DB_PATH?immutable=1" ".backup $TMP/pyweb.db"

# 2. Full B-tree walk on the snapshot. Catches any torn page that slipped
#    through. Failures abort the run so we never ship a corrupt archive.
echo "[$STAMP] Verifying DB integrity..."
result=$(sqlite3 "$TMP/pyweb.db" "PRAGMA integrity_check")
if [[ "$result" != "ok" ]]; then
    echo "ERROR: integrity_check failed: $result" >&2
    exit 1
fi

# 3. Mirror the whole data/ dir into the staging area. -a preserves
#    mode / mtime / ownership, and the trailing /. tells cp to copy the
#    contents (so a new subdir under data/ later — exports/, cache/, etc
#    — automatically lands in the bundle without a script change).
echo "[$STAMP] Mirroring $PYWEB_DATA_DIR/..."
mkdir -p "$STAGE"
cp -a "$PYWEB_DATA_DIR/." "$STAGE/"

# 4. Replace the live DB (which may have torn pages) with our snapshot,
#    and drop the SQLite coordination files — they're transient state
#    that has no meaning outside the backend container that wrote them.
mv -f "$TMP/pyweb.db" "$STAGE/pyweb.db"
rm -f "$STAGE/pyweb.db-wal" "$STAGE/pyweb.db-shm"

# 5. Bundle. -C $TMP makes the tarball's paths relative (data/pyweb.db,
#    data/uploads/...) rather than absolute /tmp/tmp.XXXX/... which
#    would be painful on restore.
echo "[$STAMP] Bundling..."
ARCHIVE="$TMP/pyweb-$STAMP.tar.gz"
tar -czf "$ARCHIVE" -C "$TMP" data

echo "[$STAMP] Uploading $(du -h "$ARCHIVE" | cut -f1) → $RCLONE_REMOTE/"
rclone copy "$ARCHIVE" "$RCLONE_REMOTE/"

# Prune old archives. --min-age means "objects with mtime older than X".
echo "[$STAMP] Pruning archives older than ${RETENTION_DAYS}d"
rclone delete --min-age "${RETENTION_DAYS}d" "$RCLONE_REMOTE/"

echo "[$STAMP] Backup complete"
