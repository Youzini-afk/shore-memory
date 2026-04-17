#!/usr/bin/env sh
set -eu

mkdir -p "${PMS_DATA_DIR:-/data}"

worker_host="${PMW_HOST:-127.0.0.1}"
worker_port="${PMW_PORT:-7812}"
server_port="${PMS_PORT:-${PORT:-7811}}"

export PMS_HOST="${PMS_HOST:-0.0.0.0}"
export PMS_PORT="$server_port"
export PMS_DATA_DIR="${PMS_DATA_DIR:-/data}"
export PMS_WEB_DIST="${PMS_WEB_DIST:-/app/web/dist}"
export PMS_WORKER_BASE_URL="${PMS_WORKER_BASE_URL:-http://${worker_host}:${worker_port}}"

python -m uvicorn app.main:app --app-dir /app/worker --host "$worker_host" --port "$worker_port" &
worker_pid=$!

trap 'kill "$worker_pid" 2>/dev/null || true' EXIT INT TERM

sleep 1
if ! kill -0 "$worker_pid" 2>/dev/null; then
  exit 1
fi

exec /app/shore-memory-server
