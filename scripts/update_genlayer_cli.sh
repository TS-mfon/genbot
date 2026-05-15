#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="${GENBOT_CLI_UPDATE_LOG:-/var/log/genbot-cli-update.log}"
SERVICE_NAME="${GENBOT_SERVICE_NAME:-genbot}"

before="$(genlayer --version 2>/dev/null || echo 'not-installed')"
npm install -g genlayer@latest --no-audit --no-fund
after="$(genlayer --version 2>/dev/null || echo 'not-installed')"

printf '%s before=%s after=%s\n' "$(date -Is)" "$before" "$after" >> "$LOG_FILE"

if [ "$before" != "$after" ] && command -v systemctl >/dev/null 2>&1; then
  systemctl restart "$SERVICE_NAME"
  printf '%s restarted=%s\n' "$(date -Is)" "$SERVICE_NAME" >> "$LOG_FILE"
fi
