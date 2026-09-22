#!/usr/bin/env bash
# Create this quickstart's Managed Agents resources with the ant CLI and save
# their IDs to .env. Re-run after editing the YAML to update them in place.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || cp .env.example .env
# Only .env decides create vs update. An ID left exported in the shell by
# another quickstart would otherwise send this YAML to that quickstart's agent.
unset CLAUDE_AGENT_ID CLAUDE_ENVIRONMENT_ID
set -a; . ./.env; set +a

if [ -z "${CLAUDE_ENVIRONMENT_ID:-}" ]; then
  CLAUDE_ENVIRONMENT_ID=$(ant beta:environments create --transform id --raw-output < agents/linear-assistant/environment.yaml)
  printf '\nCLAUDE_ENVIRONMENT_ID=%s\n' "$CLAUDE_ENVIRONMENT_ID" >> .env
  echo "environment: created $CLAUDE_ENVIRONMENT_ID"
else
  ant beta:environments update --environment-id "$CLAUDE_ENVIRONMENT_ID" < agents/linear-assistant/environment.yaml > /dev/null
  echo "environment: updated $CLAUDE_ENVIRONMENT_ID"
fi

if [ -z "${CLAUDE_AGENT_ID:-}" ]; then
  CLAUDE_AGENT_ID=$(ant beta:agents create --transform id --raw-output < agents/linear-assistant/agent.yaml)
  printf '\nCLAUDE_AGENT_ID=%s\n' "$CLAUDE_AGENT_ID" >> .env
  echo "agent: created $CLAUDE_AGENT_ID"
else
  version=$(ant beta:agents update --agent-id "$CLAUDE_AGENT_ID" --transform version --raw-output < agents/linear-assistant/agent.yaml)
  echo "agent: updated $CLAUDE_AGENT_ID (version $version)"
fi
