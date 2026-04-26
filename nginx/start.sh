#!/usr/bin/env bash
# Start a non-privileged nginx instance that serves the production-like
# frontend on :8080 and reverse-proxies /api to the FastAPI backend on
# :8000. Independent of any system-wide nginx.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="/tmp/pyweb-nginx"
CONF="${PREFIX}/pyweb.conf"

if [[ ! -d "${REPO_ROOT}/frontend/dist" ]]; then
  echo "frontend/dist not found. Build first: (cd frontend && npm run build)" >&2
  exit 1
fi

mkdir -p "${PREFIX}"
sed "s|__PYWEB_ROOT__|${REPO_ROOT}|g" "${REPO_ROOT}/nginx/pyweb.conf.template" > "${CONF}"

# -c: use our config in isolation (no merge with /etc/nginx/nginx.conf)
# -p: prefix dir for relative paths declared inside the config (pid + logs)
echo "Starting nginx on http://localhost:8080  (logs in ${PREFIX}/)"
exec nginx -c "${CONF}" -p "${PREFIX}/" "$@"
