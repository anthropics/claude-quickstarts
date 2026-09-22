#!/usr/bin/env bash
# Host-side launcher for the memory-enabled Docker demo.
#
# Builds the per-session image, then runs `ant beta:worker poll` on the host
# with --on-work pointed at on-work.sh, which `docker run`s one container per
# claimed session. The poller only claims work. It never runs tools, and it
# is the only process that ever holds the environment key.
#
# Requires: docker, jq, and `ant` on PATH.
#
# Reads the environment ID from claude-lock.json (written by `ant apply`) and
# the environment key from .env; a value set in .env wins over the same
# variable exported in the shell. On a sandbox host that has neither file,
# export these instead:
#   ANTHROPIC_ENVIRONMENT_ID   - the self-hosted environment id (env_...)
#   ANTHROPIC_ENVIRONMENT_KEY  - the environment key, minted in the Console.
#                                Stays in the poller; never enters a container.
#   ANTHROPIC_BASE_URL         - optional, default https://api.anthropic.com
set -euo pipefail
cd "$(dirname "$0")"

for bin in docker jq ant; do
  command -v "$bin" >/dev/null || { echo "$bin not found on PATH (see the README)" >&2; exit 1; }
done

if [ -f .env ]; then set -a; . ./.env; set +a; fi
# CLAUDE_ENVIRONMENT_ID is where this demo's earlier setup.sh flow kept the ID;
# honoring it lets a returning user keep their environment and its key.
ANTHROPIC_ENVIRONMENT_ID="${ANTHROPIC_ENVIRONMENT_ID:-${CLAUDE_ENVIRONMENT_ID:-}}"
if [ -z "$ANTHROPIC_ENVIRONMENT_ID" ] && [ -f claude-lock.json ]; then
  ANTHROPIC_ENVIRONMENT_ID=$(jq -r '.resources["./environments/self-hosted.yaml"].id // empty' claude-lock.json)
fi
export ANTHROPIC_ENVIRONMENT_ID
: "${ANTHROPIC_ENVIRONMENT_ID:?no environment ID: run \"ant apply .\" from this directory so claude-lock.json lands beside start.sh, or export ANTHROPIC_ENVIRONMENT_ID (env_...)}"
: "${ANTHROPIC_ENVIRONMENT_KEY:?set ANTHROPIC_ENVIRONMENT_KEY in .env (mint it in the Console for ${ANTHROPIC_ENVIRONMENT_ID})}"
export ANTHROPIC_ENVIRONMENT_KEY
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"
# The poller authenticates with the environment key alone. An org API key
# from .env has no business in the sandbox host's process tree.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN

IMAGE="${SANDBOX_IMAGE:-shs-docker-memory}"
echo "[start] building ${IMAGE}"
docker build -t "$IMAGE" .

echo "[start] polling env=${ANTHROPIC_ENVIRONMENT_ID} base=${ANTHROPIC_BASE_URL}"
# --on-work delegates each work item to on-work.sh (SANDBOX_IMAGE/ANTHROPIC_*
# are inherited). The poll side runs no tools, so its --workdir is unused;
# point it at a throwaway. Exits cleanly on SIGTERM/SIGINT.
exec env SANDBOX_IMAGE="$IMAGE" \
  ant beta:worker poll \
    --on-work "$PWD/on-work.sh" \
    --workdir /tmp \
    --log-format text
