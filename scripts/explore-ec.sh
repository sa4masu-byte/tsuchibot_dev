#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="$REPOSITORY_ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "error: .venv is missing. Run make install first." >&2
  exit 2
fi

if [[ $# -eq 0 ]]; then
  cat >&2 <<'EOF'
Usage:
  scripts/explore-ec.sh --run-id <uuid> --input <ec-manual-v1.json>

This manual fallback never purchases, messages, or lists products.
EOF
  exit 2
fi

cd "$REPOSITORY_ROOT"
exec "$PYTHON" -m worker.cli ec-manual "$@"
