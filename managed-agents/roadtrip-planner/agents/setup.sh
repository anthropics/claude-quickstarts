#!/usr/bin/env bash
# Create this quickstart's Managed Agents resources with the ant CLI and save
# their IDs to .env. Re-run after editing the YAML to update them in place.
#
# Creates, in order: the vault, two credentials, the environment, the reviewer
# agent, then the planner agent whose roster names the reviewer. Each resource
# is gated on its own ID in .env, so a run that fails partway picks up where
# it stopped.
set -euo pipefail
cd "$(dirname "$0")/.."

# .env holds three API keys, so keep it owner-only.
umask 077
[ -f .env ] || cp .env.example .env
chmod 600 .env
# .env is the only source for these IDs. Clear any copy already exported in
# this shell (a sibling quickstart uses the same names), or a fresh run here
# would update, or tear down, someone else's resources.
unset CLAUDE_VAULT_ID CLAUDE_NATIONAL_PARK_SERVICE_CREDENTIAL_ID CLAUDE_WINDY_CREDENTIAL_ID \
  CLAUDE_ENVIRONMENT_ID CLAUDE_REVIEWER_AGENT_ID CLAUDE_AGENT_ID
set -a; . ./.env; set +a

# The two keys are interpolated into a YAML body below. A quote or newline in
# one would change that body, so refuse anything that is not a plain token.
for v in NATIONAL_PARK_SERVICE_API_KEY WINDY_API_KEY; do
  [ -n "${!v:-}" ] || { echo "$v is not set in .env (see .env.example)" >&2; exit 1; }
  [[ "${!v}" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "$v has characters an API key should not. Check for quotes or spaces in .env." >&2; exit 1; }
done

save() { printf '%s=%s\n' "$1" "$2" >> .env; }

if [ -z "${CLAUDE_VAULT_ID:-}" ]; then
  CLAUDE_VAULT_ID=$(ant beta:vaults create --transform id --raw-output < agents/roadtrip-planner/vault.yaml)
  printf '\n' >> .env; save CLAUDE_VAULT_ID "$CLAUDE_VAULT_ID"
  echo "vault: created $CLAUDE_VAULT_ID"
else
  ant beta:vaults update --vault-id "$CLAUDE_VAULT_ID" < agents/roadtrip-planner/vault.yaml > /dev/null
  echo "vault: updated $CLAUDE_VAULT_ID"
fi

# Both credentials are `environment_variable` credentials: the sandbox sees
# $NATIONAL_PARK_SERVICE_API_KEY and $WINDY_API_KEY as opaque placeholders, and
# the real key is substituted into a request only when the request host is in
# the credential's allowed_hosts AND the placeholder sits somewhere
# injection_location allows. NPS wants its key in a request header and Windy
# wants it in the POST body, so each credential sets the location its vendor
# documents. Same vault, same mechanism, opposite locations.
#
# The bodies are heredocs so the keys travel on stdin. They never land in a
# YAML file and never show up in a process listing. Credentials are created
# once: to change an injection_location on a live one, see README.md, step 2.
if [ -z "${CLAUDE_NATIONAL_PARK_SERVICE_CREDENTIAL_ID:-}" ]; then
  CLAUDE_NATIONAL_PARK_SERVICE_CREDENTIAL_ID=$(ant beta:vaults:credentials create --vault-id "$CLAUDE_VAULT_ID" --transform id --raw-output <<YAML
display_name: National Park Service API key (header)
metadata:
  quickstart: roadtrip-planner
  vendor: nps
auth:
  type: environment_variable
  secret_name: NATIONAL_PARK_SERVICE_API_KEY
  secret_value: "$NATIONAL_PARK_SERVICE_API_KEY"
  networking:
    type: limited
    allowed_hosts: [developer.nps.gov]
  injection_location: {header: true, body: false}
YAML
  )
  save CLAUDE_NATIONAL_PARK_SERVICE_CREDENTIAL_ID "$CLAUDE_NATIONAL_PARK_SERVICE_CREDENTIAL_ID"
  echo "credential: created $CLAUDE_NATIONAL_PARK_SERVICE_CREDENTIAL_ID  NATIONAL_PARK_SERVICE_API_KEY -> developer.nps.gov (header)"
fi

if [ -z "${CLAUDE_WINDY_CREDENTIAL_ID:-}" ]; then
  CLAUDE_WINDY_CREDENTIAL_ID=$(ant beta:vaults:credentials create --vault-id "$CLAUDE_VAULT_ID" --transform id --raw-output <<YAML
display_name: Windy API key (body)
metadata:
  quickstart: roadtrip-planner
  vendor: windy
auth:
  type: environment_variable
  secret_name: WINDY_API_KEY
  secret_value: "$WINDY_API_KEY"
  networking:
    type: limited
    allowed_hosts: [api.windy.com]
  injection_location: {header: false, body: true}
YAML
  )
  save CLAUDE_WINDY_CREDENTIAL_ID "$CLAUDE_WINDY_CREDENTIAL_ID"
  echo "credential: created $CLAUDE_WINDY_CREDENTIAL_ID  WINDY_API_KEY -> api.windy.com (body)"
fi

if [ -z "${CLAUDE_ENVIRONMENT_ID:-}" ]; then
  CLAUDE_ENVIRONMENT_ID=$(ant beta:environments create --transform id --raw-output < agents/roadtrip-planner/environment.yaml)
  save CLAUDE_ENVIRONMENT_ID "$CLAUDE_ENVIRONMENT_ID"
  echo "environment: created $CLAUDE_ENVIRONMENT_ID"
else
  ant beta:environments update --environment-id "$CLAUDE_ENVIRONMENT_ID" < agents/roadtrip-planner/environment.yaml > /dev/null
  echo "environment: updated $CLAUDE_ENVIRONMENT_ID"
fi

# The reviewer has to exist before the planner, whose roster names it by ID.
if [ -z "${CLAUDE_REVIEWER_AGENT_ID:-}" ]; then
  CLAUDE_REVIEWER_AGENT_ID=$(ant beta:agents create --transform id --raw-output < agents/plan-reviewer/agent.yaml)
  save CLAUDE_REVIEWER_AGENT_ID "$CLAUDE_REVIEWER_AGENT_ID"
  echo "reviewer: created $CLAUDE_REVIEWER_AGENT_ID"
else
  version=$(ant beta:agents update --agent-id "$CLAUDE_REVIEWER_AGENT_ID" --transform version --raw-output < agents/plan-reviewer/agent.yaml)
  echo "reviewer: updated $CLAUDE_REVIEWER_AGENT_ID (version $version)"
fi

# The planner's YAML is a template: its roster carries the reviewer's ID.
# Render it to a file and redirect that in. Piping sed into ant races ant's
# 10 ms check for piped stdin, and an update that loses the race sends an empty
# body and still exits 0.
planner_yaml=$(mktemp)
trap 'rm -f "$planner_yaml"' EXIT
sed "s|{{CLAUDE_REVIEWER_AGENT_ID}}|$CLAUDE_REVIEWER_AGENT_ID|g" agents/roadtrip-planner/agent.yaml > "$planner_yaml"
grep -q "$CLAUDE_REVIEWER_AGENT_ID" "$planner_yaml" || { echo "agents/roadtrip-planner/agent.yaml has no {{CLAUDE_REVIEWER_AGENT_ID}} placeholder" >&2; exit 1; }

if [ -z "${CLAUDE_AGENT_ID:-}" ]; then
  CLAUDE_AGENT_ID=$(ant beta:agents create --transform id --raw-output < "$planner_yaml")
  save CLAUDE_AGENT_ID "$CLAUDE_AGENT_ID"
  echo "planner: created $CLAUDE_AGENT_ID"
else
  version=$(ant beta:agents update --agent-id "$CLAUDE_AGENT_ID" --transform version --raw-output < "$planner_yaml")
  echo "planner: updated $CLAUDE_AGENT_ID (version $version)"
fi

cat <<'DONE'

| secret                        | host              | injected in |
|-------------------------------|-------------------|-------------|
| NATIONAL_PARK_SERVICE_API_KEY | developer.nps.gov | header      |
| WINDY_API_KEY                 | api.windy.com     | body        |

Next: npm run dev  ->  http://localhost:3000
DONE
