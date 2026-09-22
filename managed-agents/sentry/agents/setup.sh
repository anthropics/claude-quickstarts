#!/usr/bin/env bash
# Provision this quickstart. `ant apply` creates or updates the agent, the
# environment, and the vault from agents/, environments/, and vaults/ and
# records their IDs in claude-lock.json. Then the one step it leaves to you,
# because no secret passes through it: the Sentry token goes into the vault as
# a credential. Re-run after editing a file: apply publishes the change, and if
# deploy.py has created the deployment, it is re-pinned to the new version.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v jq >/dev/null || { echo "jq not found on PATH (see the README)" >&2; exit 1; }
[ -f .env ] || cp .env.example .env
# Only .env decides whether a deployment exists here. One left exported by
# another quickstart would otherwise be re-pinned to this agent.
unset CLAUDE_DEPLOYMENT_ID
set -a; . ./.env; set +a

for v in SENTRY_AUTH_TOKEN SENTRY_ORG SENTRY_PROJECT; do
  [ -n "${!v:-}" ] || { echo "$v is not set in .env (see .env.example)" >&2; exit 1; }
done

# --yes: the plan is three small resources and this script is the review. Run
# `ant apply --dry-run agents environments vaults` first to see it.
ant apply --yes agents environments vaults

lock_id() { jq -r --arg f "$1" '.resources[$f].id // empty' claude-lock.json; }
vault=$(lock_id ./vaults/sentry-triage.yaml)
: "${vault:?claude-lock.json has no vault: read the ant apply output above}"

# The credential exposes SENTRY_AUTH_TOKEN inside any session this vault is
# attached to. The sandbox only ever holds an opaque placeholder: the egress
# proxy substitutes the real token on requests to allowed_hosts and nothing
# else. Created once; the vault is the record of whether it exists. To rotate
# the token later, see skill.md, "Changing env var name and values".
if ant beta:vaults:credentials list --vault-id "$vault" --max-items -1 --format jsonl \
     --transform auth.secret_name --raw-output </dev/null | grep -qx SENTRY_AUTH_TOKEN; then
  echo "credential: SENTRY_AUTH_TOKEN is already in $vault"
else
  credential=$(ant beta:vaults:credentials create --vault-id "$vault" --transform id --raw-output <<YAML
display_name: Sentry org auth token (read-only scopes)
auth:
  type: environment_variable
  secret_name: SENTRY_AUTH_TOKEN
  secret_value: "$SENTRY_AUTH_TOKEN"
  networking:
    type: limited
    allowed_hosts: [sentry.io, us.sentry.io, de.sentry.io]
YAML
  )
  echo "credential: created $credential in $vault"
fi

# The deployment keeps the agent version, environment, and vaults it was
# created with, so nothing above reaches scheduled runs on its own. deploy.py
# re-sends all three (and the org and project from .env) when the deployment
# already exists.
if [ -n "${CLAUDE_DEPLOYMENT_ID:-}" ]; then
  uv run python deploy.py
fi
