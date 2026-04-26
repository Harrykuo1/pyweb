#!/usr/bin/env bash
# Stop the pyweb-specific nginx started by ./nginx/start.sh.
set -euo pipefail

PID_FILE="/tmp/pyweb-nginx/pyweb-nginx.pid"
if [[ ! -f "${PID_FILE}" ]]; then
  echo "No pid file at ${PID_FILE}; nothing to stop." >&2
  exit 0
fi

pid="$(cat "${PID_FILE}")"
if kill -0 "${pid}" 2>/dev/null; then
  echo "Stopping pyweb-nginx (pid ${pid})"
  kill -QUIT "${pid}"
else
  echo "pid ${pid} already gone; cleaning up pid file"
  rm -f "${PID_FILE}"
fi
