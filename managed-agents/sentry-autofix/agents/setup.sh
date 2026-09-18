#!/usr/bin/env bash
# Create this quickstart's Managed Agents resources with the ant CLI. Re-run
# after editing the YAML to update them in place.
set -euo pipefail
cd "$(dirname "$0")/.."

# .env first, so an ANTHROPIC_API_KEY kept there reaches every `ant` call below.
# CLAUDE_VAULT_ID is cleared before sourcing because only .env should decide
# whether the vault exists: the Sentry triage quickstart uses the same name, and
# one left exported in this shell would skip the create and reuse its vault.
[ -f .env ] || cp .env.example .env
unset CLAUDE_VAULT_ID
set -a; . ./.env; set +a

# The agent and the environment. `ant apply` creates whatever is missing,
# updates whatever changed, and records the IDs in claude-lock.json, which is
# where the app reads them from.
ant apply --yes agents/issue-fixer

# `ant apply` does not manage vaults, so the vault is created once and its ID
# kept in .env. It starts empty: `npm run sentry-login` adds the credential.
if [ -z "${CLAUDE_VAULT_ID:-}" ]; then
  CLAUDE_VAULT_ID=$(ant beta:vaults create --transform id --raw-output < agents/issue-fixer/vault.yaml)
  printf '\nCLAUDE_VAULT_ID=%s\n' "$CLAUDE_VAULT_ID" >> .env
  echo "vault: created $CLAUDE_VAULT_ID"
fi
