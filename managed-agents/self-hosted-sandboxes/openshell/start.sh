#!/usr/bin/env bash
# Host-side launcher for the OpenShell self-hosted sandbox demo.
#
# Builds the sandbox image, then runs `ant beta:worker poll` on the host with
# --on-work pointed at on-work.sh, which runs each claimed session's worker in
# that session's own OpenShell sandbox. The poller only claims work and never
# runs tools. The environment key stays on the host: the poller passes it to
# on-work.sh, which unsets it before it calls openshell.
#
# Requires: docker, jq, `ant`, and `openshell` on PATH, and a running
# OpenShell gateway.
#
# Reads the environment ID from claude-lock.json (written by `ant apply`) and
# the environment key from .env. A value set in .env wins over the same
# variable exported in the shell. On a sandbox host that has neither file,
# export these instead:
#   ANTHROPIC_ENVIRONMENT_ID   - the self-hosted environment id (env_...)
#   ANTHROPIC_ENVIRONMENT_KEY  - the environment key, minted in the Console.
#                                Stays on the host. Never enters a sandbox.
#   ANTHROPIC_BASE_URL         - optional, default https://api.anthropic.com.
#                                policy.yaml allows that host and no other.
set -euo pipefail
cd "$(dirname "$0")"

for bin in docker jq ant openshell; do
  command -v "$bin" >/dev/null || { echo "$bin not found on PATH (see the README)" >&2; exit 1; }
done

if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ -z "${ANTHROPIC_ENVIRONMENT_ID:-}" ] && [ -f claude-lock.json ]; then
  ANTHROPIC_ENVIRONMENT_ID=$(jq -r '.resources["./environments/self-hosted.yaml"].id // empty' claude-lock.json)
fi
export ANTHROPIC_ENVIRONMENT_ID
: "${ANTHROPIC_ENVIRONMENT_ID:?no environment ID: run \"ant apply .\" from this directory so claude-lock.json lands beside start.sh, or export ANTHROPIC_ENVIRONMENT_ID (env_...)}"
: "${ANTHROPIC_ENVIRONMENT_KEY:?set ANTHROPIC_ENVIRONMENT_KEY in .env and uncomment the line (mint the key in the Console for ${ANTHROPIC_ENVIRONMENT_ID})}"
export ANTHROPIC_ENVIRONMENT_KEY
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"
# The poller authenticates with the environment key alone. An org API key
# from .env has no business in the sandbox host's process tree.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN

# Find a missing gateway now, not on the first claimed session. A real request
# is the test, because `openshell status` exits 0 with no gateway configured.
openshell sandbox list >/dev/null 2>&1 || {
  echo "no OpenShell gateway answered: run \"openshell status\" to see why (see the README)" >&2
  exit 1
}

# OpenShell takes an image reference, not a Dockerfile. A local tag needs no
# registry as long as this is the Docker engine the gateway uses.
IMAGE="${SANDBOX_IMAGE:-shs-openshell}"
echo "[start] building ${IMAGE} (ant CLI pinned in Dockerfile)"
docker build -t "$IMAGE" .

echo "[start] polling env=${ANTHROPIC_ENVIRONMENT_ID} base=${ANTHROPIC_BASE_URL}"
# --on-work delegates each work item to on-work.sh (SANDBOX_IMAGE/ANTHROPIC_*
# are inherited). The poll side runs no tools, so its --workdir is unused.
# Point it at a throwaway. Exits cleanly on SIGTERM/SIGINT.
exec env SANDBOX_IMAGE="$IMAGE" \
  ant beta:worker poll \
    --on-work "$PWD/on-work.sh" \
    --workdir /tmp \
    --log-format text
