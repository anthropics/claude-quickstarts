#!/usr/bin/env bash
# Removes everything agents/setup.sh created: archives the deployment and the agent,
# deletes the environment, both memory stores (your preferences and the agent's state
# go with them) and the vault with its two credentials, then removes claude-lock.json
# so the next `agents/setup.sh` starts fresh. Pass --yes to skip the prompt.
set -euo pipefail
cd "$(dirname "$0")/.."
for tool in ant jq; do
  command -v "$tool" >/dev/null || { echo "install $tool first (see README)" >&2; exit 1; }
done

lock_id() { jq -r ".resources[\"./agents/daily-brief/$1\"].id // empty" claude-lock.json 2>/dev/null || true; }
DEPLOYMENT=$(lock_id deployment.md); AGENT=$(lock_id agent.md); ENVIRONMENT=$(lock_id environment.yaml)
PREFS=$(lock_id memory_store_preferences.yaml); STATE=$(lock_id memory_store_state.yaml); VAULT=$(lock_id vault.yaml)
[ -n "$DEPLOYMENT$AGENT$ENVIRONMENT$PREFS$STATE$VAULT" ] || { echo "nothing to remove: claude-lock.json has no daily-brief resources" >&2; exit 0; }

printf 'This removes:\n  deployment  %s\n  agent       %s\n  environment %s\n  preferences %s\n  state       %s\n  vault       %s\n' \
  "${DEPLOYMENT:--}" "${AGENT:--}" "${ENVIRONMENT:--}" "${PREFS:--}" "${STATE:--}" "${VAULT:--}"
if [ "${1:-}" != "--yes" ]; then
  read -r -p "Go ahead? [y/N] " answer
  [ "$answer" = "y" ] || { echo "aborted"; exit 1; }
fi

# The deployment goes first so nothing can start a run against resources that are
# about to disappear. Deployments and agents are archived (the API keeps their
# history); the rest is deleted. Every step runs even if an earlier one fails, but
# claude-lock.json is only removed once all of them succeeded, so a failed run can be
# repeated after fixing the cause (not signed in, no network) without losing the IDs.
failed=
remove() { # remove <label> <ant subcommand...>
  local label=$1; shift
  ant "$@" </dev/null >/dev/null 2>&1 || { echo "  could not remove $label" >&2; failed=1; }
}
[ -z "$DEPLOYMENT" ]  || remove "deployment $DEPLOYMENT"   beta:deployments archive --deployment-id "$DEPLOYMENT"
[ -z "$AGENT" ]       || remove "agent $AGENT"             beta:agents archive --agent-id "$AGENT"
[ -z "$ENVIRONMENT" ] || remove "environment $ENVIRONMENT" beta:environments delete --environment-id "$ENVIRONMENT"
[ -z "$PREFS" ]       || remove "preferences store $PREFS" beta:memory-stores delete --memory-store-id "$PREFS"
[ -z "$STATE" ]       || remove "state store $STATE"       beta:memory-stores delete --memory-store-id "$STATE"
[ -z "$VAULT" ]       || remove "vault $VAULT"             beta:vaults delete --vault-id "$VAULT"

if [ -n "$failed" ]; then
  echo "some resources were not removed; claude-lock.json is kept so you can run this again after fixing the cause (if you already removed them elsewhere, delete claude-lock.json by hand)" >&2
  exit 1
fi
rm -f claude-lock.json
perl -pi -e 's/^vault_ids: \[.*?\]/vault_ids: []/' agents/daily-brief/deployment.md
echo "done. The Slack app and the GitHub token are yours to revoke."
