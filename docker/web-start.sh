#!/bin/sh
set -eu

PORT="${SERVER_PORT:-8000}"
export TZ="${TIMEZONE:-Europe/London}"
case "$PORT" in
    ''|*[!0-9]*) echo "ERROR: SERVER_PORT must be numeric." >&2; exit 2 ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "ERROR: SERVER_PORT is outside the valid TCP port range." >&2
    exit 2
fi

echo "Starting Orinoco web application on 0.0.0.0:$PORT"
exec python -m uvicorn orinoco.main:app --host 0.0.0.0 --port "$PORT"
