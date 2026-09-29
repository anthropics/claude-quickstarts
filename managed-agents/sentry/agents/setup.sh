#!/usr/bin/env bash
# Provision the agent, environment, and vault, then authorize Sentry MCP in a
# browser and store the refreshable credential directly in the vault.
set -euo pipefail
cd "$(dirname "$0")/.."

for tool in ant jq uv; do
  command -v "$tool" >/dev/null || { echo "$tool not found on PATH (see the README)" >&2; exit 1; }
done

[ -f .env ] || cp .env.example .env
# Only this project's .env decides whether a deployment exists. Ignore an ID
# inherited from another shell or quickstart.
unset CLAUDE_DEPLOYMENT_ID
set -a; . ./.env; set +a

# Organization and project slugs are settings, not secrets. The Claude Code
# guide supplies them after discovery through the Sentry plugin. A manual run
# can omit the flags and answer these prompts once; later runs reuse the
# recorded values from sentry-config.json.
usage() { echo "usage: $0 [--org <slug>] [--project <slug>]" >&2; exit 2; }
org=""
project=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --org) [ "$#" -ge 2 ] || usage; org="$2"; shift 2 ;;
    --project) [ "$#" -ge 2 ] || usage; project="$2"; shift 2 ;;
    *) usage ;;
  esac
done
if [ -f sentry-config.json ]; then
  [ -n "$org" ] || org=$(jq -r '.organization // empty' sentry-config.json)
  [ -n "$project" ] || project=$(jq -r '.project // empty' sentry-config.json)
fi
[ -n "$org" ] || read -r -p "Sentry organization slug: " org
[ -n "$project" ] || read -r -p "Sentry project slug: " project
slug_pattern='^[a-z0-9][a-z0-9_-]*$'
[[ "$org" =~ $slug_pattern ]] || { echo "invalid organization slug: $org" >&2; exit 2; }
[[ "$project" =~ $slug_pattern ]] || { echo "invalid project slug: $project" >&2; exit 2; }
jq -n --arg organization "$org" --arg project "$project" \
  '{organization: $organization, project: $project}' > sentry-config.json

# `ant apply` creates or updates the version-controlled resources and records
# their IDs in claude-lock.json.
ant apply --yes agents environments vaults

lock_id() { jq -r --arg f "$1" '.resources[$f].id // empty' claude-lock.json; }
vault=$(lock_id ./vaults/sentry-triage.yaml)
: "${vault:?claude-lock.json has no vault: read the ant apply output above}"

# The MCP credential is keyed to the exact URL declared in the agent. Claude
# Code's plugin keeps its own OAuth private; oauth_setup.py obtains a separate
# grant for unattended sessions, creates the credential with
# `ant beta:vaults:credentials create`, and probes it with mcp-oauth-validate.
# Anthropic refreshes it from this vault. Created once; the vault is the record
# of whether it exists (archived credentials are not listed, so archiving one
# and re-running this script re-authorizes: see the README).
if ant beta:vaults:credentials list --vault-id "$vault" --max-items -1 --format jsonl \
     --transform auth.mcp_server_url --raw-output </dev/null \
     | grep -qx 'https://mcp.sentry.dev/mcp'; then
  echo "credential: Sentry MCP OAuth is already in $vault"
else
  uv run python oauth_setup.py --vault-id "$vault"
fi

# A deployment pins its agent version and initial message. Re-apply those
# values when setup is re-run after an edit or org/project change.
if [ -n "${CLAUDE_DEPLOYMENT_ID:-}" ]; then
  uv run python deploy.py
fi
