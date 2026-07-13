#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="$REPOSITORY_ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "error: run 'make install' first." >&2
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
