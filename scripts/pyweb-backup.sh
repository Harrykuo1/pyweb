#!/usr/bin/env bash
# Consistent PostgreSQL dump plus uploaded files and recovery metadata.
# Run from the repository root as the normal deployment user. Existing
# PYWEB_DATA_DIR / RCLONE_REMOTE / RETENTION_DAYS and cron commands still work.
# Uploaded files are copied live; pause writes for a coordinated DB+file snapshot.
# Restore instructions: docs/postgresql-migration.md.

set -euo pipefail

PYWEB_DATA_DIR="${PYWEB_DATA_DIR:-./data}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:pyweb-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

if [[ ! -d "$PYWEB_DATA_DIR" ]]; then
    echo "ERROR: $PYWEB_DATA_DIR is not a directory" >&2
    exit 1
fi

for cmd in docker tar gzip rclone; do
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

# Never copy a running PostgreSQL data directory as a backup.
echo "[$STAMP] Dumping PostgreSQL..."
mkdir -p "$STAGE"
docker compose exec -T postgres pg_dump -U pyweb -d pyweb --format=custom > "$STAGE/postgres.dump"
docker compose exec -T postgres pg_restore --list < "$STAGE/postgres.dump" > /dev/null

echo "[$STAMP] Copying uploads and recovery metadata..."
tar -C "$PYWEB_DATA_DIR" \
    --exclude='./postgresql' --exclude='./postgres.dump' \
    --exclude='./pyweb.db-wal' --exclude='./pyweb.db-shm' -cf - . \
    | tar -C "$STAGE" -xf -

echo "[$STAMP] Bundling..."
ARCHIVE="$TMP/pyweb-$STAMP.tar.gz"
tar -czf "$ARCHIVE" -C "$TMP" data

echo "[$STAMP] Uploading $(du -h "$ARCHIVE" | cut -f1) → $RCLONE_REMOTE/"
rclone copy "$ARCHIVE" "$RCLONE_REMOTE/"

# Prune old archives. --min-age means "objects with mtime older than X".
echo "[$STAMP] Pruning archives older than ${RETENTION_DAYS}d"
rclone delete --min-age "${RETENTION_DAYS}d" "$RCLONE_REMOTE/"

echo "[$STAMP] Backup complete"
