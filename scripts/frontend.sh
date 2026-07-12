#!/usr/bin/env bash

set -Eeuo pipefail

REPOSITORY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPOSITORY_ROOT"

if command -v pnpm >/dev/null 2>&1; then
  exec pnpm --dir frontend "$@"
fi

if command -v corepack >/dev/null 2>&1; then
  exec corepack pnpm --dir frontend "$@"
fi

if command -v npx >/dev/null 2>&1; then
  echo "pnpm was not found; using npx pnpm@10.13.1" >&2
  exec npx --yes pnpm@10.13.1 --dir frontend "$@"
fi

echo "error: Node.js is required. Install Node.js 20.9 or newer." >&2
exit 1
