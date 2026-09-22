#!/usr/bin/env bash
# Host-side launcher. Runs WORKERS copies of `ant beta:worker poll` with
# --on-work pointed at on-work.py, which runs each claimed session in its own
# Archil sandbox and stays attached to it. One poller serves one session at a
# time, so WORKERS is the number of sessions that can run at once (default 3).
#
# Requires: `ant` and jq on PATH and python3 with the archil SDK (pip install
# -r requirements.txt). Reads the environment ID from claude-lock.json (written
# by `ant apply`) unless ANTHROPIC_ENVIRONMENT_ID is exported, and .env for
# ARCHIL_* (the API key creates sandboxes from the host; the mount token goes
# into each sandbox) and
#   ANTHROPIC_ENVIRONMENT_KEY  - the environment key, minted in the Console
set -euo pipefail
cd "$(dirname "$0")"

for bin in ant jq python3; do
  command -v "$bin" >/dev/null || { echo "$bin not found on PATH (see the README)" >&2; exit 1; }
done
python3 -c 'import archil' 2>/dev/null || { echo "archil SDK not found: pip install -r requirements.txt" >&2; exit 1; }

if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ -z "${ANTHROPIC_ENVIRONMENT_ID:-}" ] && [ -f claude-lock.json ]; then
  ANTHROPIC_ENVIRONMENT_ID=$(jq -r '.resources["./environments/self-hosted.yaml"].id // empty' claude-lock.json)
fi
export ANTHROPIC_ENVIRONMENT_ID
: "${ANTHROPIC_ENVIRONMENT_ID:?no environment ID: run \"ant apply .\" from this directory so claude-lock.json lands beside start.sh, or export ANTHROPIC_ENVIRONMENT_ID (env_...)}"
: "${ANTHROPIC_ENVIRONMENT_KEY:?set ANTHROPIC_ENVIRONMENT_KEY in .env (mint it in the Console for ${ANTHROPIC_ENVIRONMENT_ID})}"
: "${ARCHIL_API_KEY:?set ARCHIL_API_KEY in .env}"
: "${ARCHIL_MOUNT_TOKEN:?set ARCHIL_MOUNT_TOKEN in .env}"
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"
# The poller authenticates with the environment key alone.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN

WORKERS="${WORKERS:-3}"
echo "[start] polling env=${ANTHROPIC_ENVIRONMENT_ID} with ${WORKERS} workers"
trap 'kill 0' INT TERM
for i in $(seq "$WORKERS"); do
  # The poll side runs no tools, so its --workdir is unused; point it at a throwaway.
  ant beta:worker poll --on-work "$(pwd -P)/on-work.py" --workdir /tmp --log-format text 2>&1 | sed -u "s/^/[worker $i] /" &
done
wait
