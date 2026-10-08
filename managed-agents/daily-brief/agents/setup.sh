#!/usr/bin/env bash
# Create this quickstart's Managed Agents resources with the ant CLI, then hand
# over to scripts/credentials.sh for the two secrets. Safe to re-run: it updates
# what changed and skips what already exists.
#
# Needs: `ant` 1.34 or later signed in (`ant auth login`, or ANTHROPIC_API_KEY
# exported) and `jq`. No .env: the Slack and GitHub tokens are typed at a hidden
# prompt and go straight into the vault.
set -euo pipefail
cd "$(dirname "$0")/.."

for tool in ant jq curl; do
  command -v "$tool" >/dev/null || { echo "install $tool first (see README)" >&2; exit 1; }
done

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

# 2. Attach the vault to the deployment. A deployment takes vault IDs, not file
#    references, so the ID from claude-lock.json is written into deployment.md
#    (a no-op once it is there) and applied.
perl -pi -e "s/^vault_ids: \[.*?\]/vault_ids: [$VAULT_ID]/" agents/daily-brief/deployment.md
ant apply --yes agents/daily-brief/deployment.md
echo "vault: $VAULT_ID attached to the deployment"

# 3. The credentials. `ant apply` manages the vault, never what is inside it.
#    scripts/credentials.sh asks for the Slack and GitHub tokens at a hidden
#    prompt, checks each against its service, and adds it to the vault. It needs
#    a person at a terminal; when this script runs without one (from a coding
#    agent, say), that step is left for you to run yourself.
rc=0
trap 'rc=130' INT # a Ctrl-C at the prompt stops that step, not the summary below
scripts/credentials.sh || rc=$?
trap - INT
case $rc in
  0) pending="" ;;
  3 | 130) pending=1 ;; # no terminal here (3) or interrupted (130): the user does this step next
  *) pending=1; echo "credentials: scripts/credentials.sh failed (exit $rc); see its message above and run it again" >&2 ;;
esac

cat <<EOF

Next:${pending:+
  scripts/credentials.sh                                  add the Slack and GitHub tokens, in your own terminal (needed before a run)}
  cp preferences.example.md preferences.md               then put who you are, your channel IDs and repositories in it
  scripts/seed-preferences.sh preferences.md              write it into the preferences store (the agent reads it every run)
  scripts/run.sh                                          start one run now and print what the agent did
  ant beta:deployments unpause --deployment-id $DEPLOYMENT_ID   turn the schedule on once a run looks right
EOF
case $rc in 0 | 3 | 130) ;; *) exit "$rc" ;; esac
