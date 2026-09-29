#!/usr/bin/env bash
# Create this quickstart's Managed Agents resources with the ant CLI. Safe to
# re-run: it updates what changed and skips what already exists.
#
# Needs: `ant` 1.34 or later signed in (`ant auth login` or ANTHROPIC_API_KEY),
# `jq`, and a .env with SLACK_BOT_TOKEN and GITHUB_TOKEN filled in.
set -euo pipefail
cd "$(dirname "$0")/.."

for tool in ant jq; do
  command -v "$tool" >/dev/null || { echo "install $tool first (see README)" >&2; exit 1; }
done

[ -f .env ] || cp .env.example .env
set -a; . ./.env; set +a
if [ -z "${SLACK_BOT_TOKEN:-}" ] || [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "fill in SLACK_BOT_TOKEN and GITHUB_TOKEN in .env, then run this again" >&2
  exit 1
fi

first_run=true
[ -f claude-lock.json ] && jq -e '.resources["./agents/daily-brief/deployment.md"]' claude-lock.json >/dev/null 2>&1 && first_run=false

# 1. All six resources. `ant apply` follows the references in deployment.md to
#    the agent, environment and memory stores, creates the vault from
#    vault.yaml, creates whatever is missing, updates whatever changed, and
#    records the IDs in claude-lock.json.
ant apply --yes agents/daily-brief/deployment.md agents/daily-brief/vault.yaml
DEPLOYMENT_ID=$(jq -r '.resources["./agents/daily-brief/deployment.md"].id' claude-lock.json)
VAULT_ID=$(jq -r '.resources["./agents/daily-brief/vault.yaml"].id' claude-lock.json)

# Keep the schedule off until you have seen a good run (step 5 of the README).
if $first_run; then
  ant beta:deployments pause --deployment-id "$DEPLOYMENT_ID" >/dev/null
  echo "deployment: created $DEPLOYMENT_ID (paused until you unpause it)"
fi

# 2. The credentials. `ant apply` manages the vault, never what is inside it,
#    so the two credentials are added here, once, from .env. The bodies are
#    built with jq, which reads the tokens from the environment (.env was
#    exported above) and escapes whatever they contain, and reach ant on stdin
#    as here-strings (written before ant starts, unlike a pipe), so the tokens
#    never appear on any command line (visible in `ps`).
if [ "$(ant beta:vaults:credentials list --vault-id "$VAULT_ID" --format jsonl --transform id | wc -l)" -eq 0 ]; then
  # Slack: the sandbox sees a placeholder in $SLACK_BOT_TOKEN; the real token is
  # substituted at egress, on requests to slack.com only, and only in headers.
  slack_credential=$(jq -n '{
    display_name: "SLACK_BOT_TOKEN",
    auth: {
      type: "environment_variable",
      secret_name: "SLACK_BOT_TOKEN",
      secret_value: $ENV.SLACK_BOT_TOKEN,
      networking: {type: "limited", allowed_hosts: ["slack.com"]},
      injection_location: {header: true}
    }
  }')
  ant beta:vaults:credentials create --vault-id "$VAULT_ID" >/dev/null <<<"$slack_credential"
  # GitHub: matched to the MCP server in agent.md by URL.
  github_credential=$(jq -n '{
    display_name: "GitHub (read-only)",
    auth: {type: "static_bearer", mcp_server_url: "https://api.githubcopilot.com/mcp/", token: $ENV.GITHUB_TOKEN}
  }')
  ant beta:vaults:credentials create --vault-id "$VAULT_ID" >/dev/null <<<"$github_credential"
  unset slack_credential github_credential
  echo "vault: added the Slack and GitHub credentials to $VAULT_ID"
fi

# 3. Attach the vault to the deployment. A deployment takes vault IDs, not file
#    references, so the ID from claude-lock.json is written into deployment.md
#    (a no-op once it is there) and applied.
perl -pi -e "s/^vault_ids: \[.*?\]/vault_ids: [$VAULT_ID]/" agents/daily-brief/deployment.md
ant apply --yes agents/daily-brief/deployment.md

cat <<EOF

Done. Next:
  cp preferences.example.md preferences.md               then put who you are, your channel IDs and repositories in it
  scripts/seed-preferences.sh preferences.md              write it into the preferences store (the agent reads it every run)
  scripts/run.sh                                          start one run now and print what the agent did
  ant beta:deployments unpause --deployment-id $DEPLOYMENT_ID   turn the schedule on once a run looks right
EOF
