#!/usr/bin/env bash
# Create this quickstart's Managed Agents resources with the ant CLI, then
# sign in to the Sentry MCP server if the vault has no credential for it yet.
# Re-run after editing the YAML to update the resources in place.
set -euo pipefail
cd "$(dirname "$0")/.."

for tool in ant jq npm; do
  command -v "$tool" >/dev/null || { echo "$tool not found on PATH (see the README)" >&2; exit 1; }
done

# .env first, so an ANTHROPIC_API_KEY kept there reaches every `ant` call below.
[ -f .env ] || cp .env.example .env
set -a; . ./.env; set +a

# The agent, the environment, and the vault. `ant apply` creates whatever is
# missing, updates whatever changed, and records the IDs in claude-lock.json,
# which is where the app reads them from.
ant apply --yes agents/issue-fixer

vault=$(jq -r '.resources["./agents/issue-fixer/vault.yaml"].id // empty' claude-lock.json)
: "${vault:?claude-lock.json has no vault: read the ant apply output above}"

# `ant apply` manages the vault, never what is inside it. The credential is
# keyed to the exact URL declared in agent.yaml. Claude Code's Sentry plugin
# keeps its own OAuth private, so `npm run sentry-login` obtains a separate
# grant for unattended sessions, stores it, and probes it. The vault is the
# record of whether it exists. To sign in again later, run `npm run
# sentry-login` yourself: it replaces the old credential.
if ant beta:vaults:credentials list --vault-id "$vault" --max-items -1 --format jsonl \
     --transform auth.mcp_server_url --raw-output </dev/null \
     | grep -qx 'https://mcp.sentry.dev/mcp'; then
  echo "credential: Sentry MCP OAuth is already in $vault"
else
  [ -d node_modules ] || npm install
  npm run --silent sentry-login
fi
