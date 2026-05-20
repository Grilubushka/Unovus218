#!/bin/sh
set -eu

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "TELEGRAM_BOT_TOKEN is required" >&2
  exit 1
fi

mkdir -p /app/data
if [ ! -f "${DATABASE_PATH:-/app/data/bot.sqlite3}" ] && [ -f /app/seed/bot.sqlite3 ]; then
  cp /app/seed/bot.sqlite3 "${DATABASE_PATH:-/app/data/bot.sqlite3}"
fi

python -m bot.infrastructure.miniapp_server &
STATIC_PID="$!"

cleanup() {
  kill "$STATIC_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

if [ "${SETUP_TELEGRAM:-false}" = "true" ]; then
  python -m bot.setup_telegram
fi

python -m bot.main
