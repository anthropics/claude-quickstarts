#!/usr/bin/env bash
# Sandbox host for the policy reference. It runs ../openshell's poller and
# on-work.sh unchanged, with dispatcher/hook.sh as their ON_WORK_HOOK: every
# session's profile, starting policy and stop checks come from agentpolicy.
#
# Requires: docker, jq, `ant`, `openshell`, agentpolicy and openshell-prover on
# PATH, and a running OpenShell gateway.
#
# The environment ID comes from claude-lock.json (written by `ant apply`), the
# environment key from .env, as in ../openshell. Exported values work too:
#   ANTHROPIC_ENVIRONMENT_ID   the self-hosted environment (env_...)
#   ANTHROPIC_ENVIRONMENT_KEY  its key. Stays on this host; never enters a sandbox.
#   ANTHROPIC_BASE_URL         optional, default https://api.anthropic.com
# SKIP_BUILD=1 uses the images `make image` built.
set -euo pipefail
cd "$(dirname "$0")"
AGENTPOLICY="${AGENTPOLICY:-agentpolicy}"

for bin in docker jq ant openshell "$AGENTPOLICY" "${AGENTPOLICY_PROVER:-openshell-prover}"; do
  command -v "$bin" >/dev/null || { echo "$bin not found on PATH (see the README)" >&2; exit 1; }
done

# shellcheck source=/dev/null
if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ -z "${ANTHROPIC_ENVIRONMENT_ID:-}" ] && [ -f claude-lock.json ]; then
  ANTHROPIC_ENVIRONMENT_ID=$(jq -r '.resources["./environments/worker.yaml"].id // empty' claude-lock.json)
fi
export ANTHROPIC_ENVIRONMENT_ID
: "${ANTHROPIC_ENVIRONMENT_ID:?no environment ID: run \"make apply\" from this directory, or export ANTHROPIC_ENVIRONMENT_ID (env_...)}"
: "${ANTHROPIC_ENVIRONMENT_KEY:?set ANTHROPIC_ENVIRONMENT_KEY in .env (mint the key in the Console for ${ANTHROPIC_ENVIRONMENT_ID})}"
export ANTHROPIC_ENVIRONMENT_KEY
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"
# The sandbox host runs on the environment key alone. An org credential from
# .env has no business in its process tree.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN

# A real request, because `openshell status` exits 0 with no gateway configured.
openshell sandbox list >/dev/null 2>&1 || {
  echo "no OpenShell gateway answered: run \"openshell status\" to see why (see the README)" >&2
  exit 1
}

# A qualified name: some gateways resolve a bare one against a registry.
IMAGE="${SANDBOX_IMAGE:-localhost/shs-openshell-policy:latest}"
if [ -z "${SKIP_BUILD:-}" ]; then
  echo "[start] building shs-openshell (../openshell) and ${IMAGE}"
  docker build -t shs-openshell ../openshell
  docker build -t "$IMAGE" sandbox/
fi

app_label="$("$AGENTPOLICY" setting sandbox_label)"
sandbox_url="$("$AGENTPOLICY" setting sandbox_base_url)"
echo "[start] polling env=${ANTHROPIC_ENVIRONMENT_ID} base=${ANTHROPIC_BASE_URL} sandbox base=${sandbox_url}"
exec env \
  SANDBOX_IMAGE="$IMAGE" \
  SANDBOX_APP_LABEL="$app_label" \
  SANDBOX_BASE_URL="$sandbox_url" \
  ON_WORK_HOOK="$PWD/dispatcher/hook.sh" \
  ant beta:worker poll \
    --on-work "$PWD/../openshell/on-work.sh" \
    --workdir /tmp \
    --log-format text
