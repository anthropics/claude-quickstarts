#!/usr/bin/env bash
# Create this quickstart's Managed Agents resources with the ant CLI and save
# their IDs to .env. Re-run after editing the YAML to update them in place.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || cp .env.example .env
set -a; . ./.env; set +a

for v in SENTRY_AUTH_TOKEN SENTRY_ORG SENTRY_PROJECT; do
  [ -n "${!v:-}" ] || { echo "$v is not set in .env (see .env.example)" >&2; exit 1; }
done

if [ -z "${CLAUDE_VAULT_ID:-}" ]; then
  CLAUDE_VAULT_ID=$(ant beta:vaults create --transform id --raw-output < agents/sentry-triage/vault.yaml)
  printf '\nCLAUDE_VAULT_ID=%s\n' "$CLAUDE_VAULT_ID" >> .env
  echo "vault: created $CLAUDE_VAULT_ID"
else
  ant beta:vaults update --vault-id "$CLAUDE_VAULT_ID" < agents/sentry-triage/vault.yaml > /dev/null
  echo "vault: updated $CLAUDE_VAULT_ID"
fi

# Gated on its own ID, not the vault's: if this create fails after the vault ID
# is already saved, the next run has to come back here.
if [ -z "${CLAUDE_CREDENTIAL_ID:-}" ]; then
  # The credential exposes SENTRY_AUTH_TOKEN inside any session this vault is
  # attached to. The sandbox only ever holds an opaque placeholder: the egress
  # proxy substitutes the real token on requests to allowed_hosts and nothing
  # else. To rotate the token later, see skill.md, "Changing env var name and
  # values".
  CLAUDE_CREDENTIAL_ID=$(ant beta:vaults:credentials create --vault-id "$CLAUDE_VAULT_ID" --transform id --raw-output <<YAML
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
  printf 'CLAUDE_CREDENTIAL_ID=%s\n' "$CLAUDE_CREDENTIAL_ID" >> .env
  echo "credential: created $CLAUDE_CREDENTIAL_ID"
fi

if [ -z "${CLAUDE_ENVIRONMENT_ID:-}" ]; then
  CLAUDE_ENVIRONMENT_ID=$(ant beta:environments create --transform id --raw-output < agents/sentry-triage/environment.yaml)
  printf '\nCLAUDE_ENVIRONMENT_ID=%s\n' "$CLAUDE_ENVIRONMENT_ID" >> .env
  echo "environment: created $CLAUDE_ENVIRONMENT_ID"
else
  ant beta:environments update --environment-id "$CLAUDE_ENVIRONMENT_ID" < agents/sentry-triage/environment.yaml > /dev/null
  echo "environment: updated $CLAUDE_ENVIRONMENT_ID"
fi

# agent.yaml is a template: the system prompt names the Sentry org and project.
# Render it to a file and redirect that in. Piping sed into ant races ant's
# 10 ms check for piped stdin, and an update that loses the race sends an empty
# body and still exits 0.
agent_yaml=$(mktemp)
trap 'rm -f "$agent_yaml"' EXIT
sed -e "s|{{SENTRY_ORG}}|$SENTRY_ORG|g" -e "s|{{SENTRY_PROJECT}}|$SENTRY_PROJECT|g" agents/sentry-triage/agent.yaml > "$agent_yaml"

if [ -z "${CLAUDE_AGENT_ID:-}" ]; then
  CLAUDE_AGENT_ID=$(ant beta:agents create --transform id --raw-output < "$agent_yaml")
  printf '\nCLAUDE_AGENT_ID=%s\n' "$CLAUDE_AGENT_ID" >> .env
  echo "agent: created $CLAUDE_AGENT_ID"
else
  version=$(ant beta:agents update --agent-id "$CLAUDE_AGENT_ID" --transform version --raw-output < "$agent_yaml")
  echo "agent: updated $CLAUDE_AGENT_ID (version $version)"
fi

# The deployment keeps the agent version, environment, and vaults it was
# created with, so nothing above reaches scheduled runs on its own. Passing the
# bare agent ID re-pins it to the latest version. The other two matter after
# you recreate a vault or environment (delete its ID from .env and re-run).
if [ -n "${CLAUDE_DEPLOYMENT_ID:-}" ]; then
  ant beta:deployments update --deployment-id "$CLAUDE_DEPLOYMENT_ID" > /dev/null <<YAML
agent: $CLAUDE_AGENT_ID
environment_id: $CLAUDE_ENVIRONMENT_ID
vault_ids: [$CLAUDE_VAULT_ID]
YAML
  echo "deployment: synced $CLAUDE_DEPLOYMENT_ID to the agent, environment, and vault above"
fi
