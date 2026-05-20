#!/bin/sh
set -eu

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "TELEGRAM_BOT_TOKEN is required" >&2
  exit 1
fi

python -m http.server "${MINIAPP_PORT:-8080}" --directory /app/miniapp &
STATIC_PID="$!"

cleanup() {
  kill "$STATIC_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

if [ "${SETUP_TELEGRAM:-false}" = "true" ]; then
  python -m bot.setup_telegram
fi

python -m bot.main
