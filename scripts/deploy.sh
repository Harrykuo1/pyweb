#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Build while the previous release still serves traffic. Stop every writer,
# including the retired sqlite-web container, before taking the SQLite snapshot.
docker compose build
docker compose down --remove-orphans
if ! docker compose up -d --remove-orphans --wait --wait-timeout 900; then
    docker compose logs --tail=100 backend postgres db-init adminer >&2
    echo "Deployment failed. Persistent data and SQLite snapshots were retained." >&2
    exit 1
fi
docker compose ps
