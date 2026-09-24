#!/bin/sh
# Build the pre-M3 console (git tag v0-ui) for the user study, served at /legacy.
#
# The only change to that UI is study/legacy/legacy-adapter.patch: open a stored plan with
# ?decision=<id>, and send the reason code the API now requires. Output: public/legacy/, which
# Vite copies into dist/legacy. Uses the development sign-in (VITE_DEV_AUTH=true).
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'git -C "$ROOT" worktree remove --force "$WORK/v0-ui" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT
git -C "$ROOT" worktree add --detach "$WORK/v0-ui" v0-ui >/dev/null
git -C "$WORK/v0-ui" apply "$ROOT/study/legacy/legacy-adapter.patch"
cd "$WORK/v0-ui"
npm ci --no-audit --no-fund --loglevel=error
npx tsc -b
VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:8000}" VITE_DEV_AUTH=true \
  npx vite build --base /legacy/ --outDir "$ROOT/public/legacy" --emptyOutDir
echo "legacy console built into public/legacy (tag v0-ui + study adapter)"
