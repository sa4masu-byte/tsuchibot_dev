#!/usr/bin/env bash

set -Eeuo pipefail

REPOSITORY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPOSITORY_ROOT"

if [[ ! -x .venv/bin/python || ! -x .venv/bin/uvicorn ]]; then
  echo "error: Python environment is not installed. Run 'make install' first." >&2
  exit 1
fi

if [[ -n "${TSUCHIBOT_LAN_HOST:-}" ]]; then
  lan_host="$TSUCHIBOT_LAN_HOST"
else
  if ! command -v networksetup >/dev/null 2>&1 || ! command -v ipconfig >/dev/null 2>&1; then
    echo "error: Set TSUCHIBOT_LAN_HOST to the Wi-Fi IPv4 address on this computer." >&2
    exit 1
  fi
  wifi_device="$(networksetup -listallhardwareports | awk '/^Hardware Port: Wi-Fi$/ {getline; sub(/^Device: /, ""); print; exit}')"
  lan_host="$(ipconfig getifaddr "$wifi_device" 2>/dev/null || true)"
  if [[ -z "$lan_host" ]]; then
    echo "error: No Wi-Fi IPv4 address was found. Connect to Wi-Fi or set TSUCHIBOT_LAN_HOST." >&2
    exit 1
  fi
fi

if ! .venv/bin/python - <<'PY'
from backend.app.shared.config import get_settings

settings = get_settings()
if settings.production:
    raise SystemExit("error: The LAN HTTP launcher is for a trusted home network, not production.")
if settings.shared_password == "change-me" or len(settings.shared_password) < 12:
    raise SystemExit("error: Set a unique TSUCHIBOT_SHARED_PASSWORD (at least 12 characters) in .env.")
if (
    settings.session_secret.startswith("development-only-")
    or settings.session_secret.startswith("replace-with-")
    or len(settings.session_secret) < 32
):
    raise SystemExit("error: Set a unique TSUCHIBOT_SESSION_SECRET (at least 32 characters) in .env.")
if settings.session_secure:
    raise SystemExit("error: Set TSUCHIBOT_SESSION_SECURE=false for home HTTP access.")
PY
then
  exit 1
fi

if ! .venv/bin/python - <<'PY'
from urllib.parse import urlsplit

from backend.app.shared.config import get_settings

database_url = get_settings().database_url
if database_url and urlsplit(database_url).scheme not in {"postgres", "postgresql"}:
    raise SystemExit(1)
PY
then
  echo "warning: TSUCHIBOT_DATABASE_URL is not a PostgreSQL URI." >&2
  echo "warning: This LAN session will run without persistent data or live GitHub dispatch." >&2
  export TSUCHIBOT_DATABASE_URL=
  export TSUCHIBOT_GITHUB_REPOSITORY=
  export TSUCHIBOT_GITHUB_TOKEN=
fi

export NEXT_PUBLIC_API_BASE_URL=/api/v1
export NEXT_PUBLIC_SITE_URL="http://$lan_host:3000"
export TSUCHIBOT_BACKEND_URL=http://127.0.0.1:8001

echo "Building the web app for http://$lan_host:3000 ..."
./scripts/frontend.sh build

backend_pid=""
cleanup() {
  if [[ -n "$backend_pid" ]]; then
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if curl --silent --fail --max-time 1 http://127.0.0.1:8001/api/v1/health >/dev/null; then
  echo "error: LAN backend port 8001 is already in use. Stop the previous LAN session." >&2
  exit 1
fi

.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 &
backend_pid=$!
ready=false
for _ in {1..30}; do
  if curl --silent --fail --max-time 1 http://127.0.0.1:8001/api/v1/health >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  echo "error: The backend did not become ready on 127.0.0.1:8001." >&2
  exit 1
fi

echo "Open http://$lan_host:3000 on devices connected to the same Wi-Fi."
echo "Keep this terminal open. Do not forward port 3000 on your router."
./scripts/frontend.sh start --hostname "$lan_host" --port 3000
