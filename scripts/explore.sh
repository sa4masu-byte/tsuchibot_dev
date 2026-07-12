#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON="$REPOSITORY_ROOT/.venv/bin/python"

usage() {
  cat <<'EOF'
Usage:
  scripts/explore.sh [incremental]
  scripts/explore.sh full
  scripts/explore.sh retry_failed <target-run-id>

Modes:
  incremental   Process new and changed products (default).
  full          Reprocess all eligible products.
  retry_failed  Retry failed items from the specified run.
EOF
}

mode="${1:-incremental}"
target_run_id="${2:-}"

case "$mode" in
  incremental | full)
    if [[ -n "$target_run_id" ]]; then
      echo "error: $mode does not accept a target run ID" >&2
      usage >&2
      exit 2
    fi
    ;;
  retry_failed)
    if [[ -z "$target_run_id" ]]; then
      echo "error: retry_failed requires a target run ID" >&2
      usage >&2
      exit 2
    fi
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    echo "error: unsupported exploration mode: $mode" >&2
    usage >&2
    exit 2
    ;;
esac

if [[ ! -x "$PYTHON" ]]; then
  echo "error: Python environment is not installed." >&2
  echo "Run 'make install' from $REPOSITORY_ROOT first." >&2
  exit 1
fi

cd "$REPOSITORY_ROOT"

args=(explore --mode "$mode")
args+=(--source-mode "${TSUCHIBOT_SOURCE_MODE:-live}")
if [[ -n "$target_run_id" ]]; then
  args+=(--target-run-id "$target_run_id")
fi

echo "Starting Tsuchibot exploration (mode=$mode)"
exec "$PYTHON" -m worker.cli "${args[@]}"
