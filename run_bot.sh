#!/usr/bin/env bash
set -euo pipefail

cd /opt/bots/genbot

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

exec /opt/bots/genbot/.venv/bin/python -c "from bot.main import main_cli; main_cli()"
