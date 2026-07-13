#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$REPOSITORY_ROOT/.venv/bin/python"

if [[ -x "$VENV_PYTHON" ]]; then
  PYTHON="$VENV_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  echo "error: Python 3 is not installed." >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  cat >&2 <<'EOF'
Usage:
  scripts/research-mercari-browser.sh \
    --source-product-id <uuid> --run-id <uuid> [--headless]

The default opens a visible browser. CAPTCHA, login requirements, and access blocks stop the run.
EOF
  exit 2
fi

cd "$REPOSITORY_ROOT"
exec "$PYTHON" -m worker.cli research-browser "$@"
