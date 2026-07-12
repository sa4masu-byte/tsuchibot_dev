#!/usr/bin/env bash

set -Eeuo pipefail

REPOSITORY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$REPOSITORY_ROOT/.venv/bin/python"
UVICORN="$REPOSITORY_ROOT/.venv/bin/uvicorn"

if curl --silent --fail --max-time 1 http://127.0.0.1:8000/api/v1/health \
  | grep --quiet '"service":"tsuchibot-api"'; then
  echo "Tsuchibot backend is already running at http://localhost:8000"
  exit 0
fi

if [[ ! -x "$PYTHON" || ! -x "$UVICORN" ]]; then
  echo "error: Python environment is not installed. Run 'make install' first." >&2
  exit 1
fi

cd "$REPOSITORY_ROOT"
exec "$UVICORN" backend.app.main:app --reload
