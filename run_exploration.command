#!/usr/bin/env bash

set -Eeuo pipefail

REPOSITORY_ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
if [[ $# -eq 0 ]]; then
  set -- incremental
fi
exec "$REPOSITORY_ROOT/scripts/explore.sh" "$@"
