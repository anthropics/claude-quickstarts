#!/usr/bin/env bash
# Archive everything ./agents/setup.sh created, plus any sessions started from
# the UI, and remove each ID from .env once its resource is archived. Archive,
# not delete: the event logs stay readable in the Console. Afterwards
# ./agents/setup.sh starts from scratch.
#
# Safe to re-run. An ID stays in .env only while its archive keeps failing, so
# fix the cause and run this again.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

[ -f .env ] || { echo "Nothing to tear down: no .env here."; exit 0; }
# .env is the only source for these IDs. Clear any copy already exported in
# this shell (a sibling quickstart uses the same names), or a fresh run here
# would update, or tear down, someone else's resources.
unset CLAUDE_VAULT_ID CLAUDE_NATIONAL_PARK_SERVICE_CREDENTIAL_ID CLAUDE_WINDY_CREDENTIAL_ID \
  CLAUDE_ENVIRONMENT_ID CLAUDE_REVIEWER_AGENT_ID CLAUDE_AGENT_ID
set -a; . ./.env; set +a

failed=0

forget() { sed -i.bak "/^$1=/d" .env && rm -f .env.bak; }

# archive <label> <ENV_NAME> <ant args...>: archive one resource, and forget
# its ID only when that worked or the API says it is already archived or gone.
archive() {
  local label=$1 name=$2 id=${!2:-}; shift 2
  [ -n "$id" ] || return 0
  local out
  if out=$(ant "$@" 2>&1 > /dev/null); then
    echo "archived  $label $id"; forget "$name"
  elif grep -qiE 'already archived|not[ _]found|404' <<<"$out"; then
    echo "gone      $label $id"; forget "$name"
  else
    echo "FAILED    $label $id: $(tail -n 1 <<<"$out" | cut -c1-160)" >&2; failed=1
  fi
}

if [ -z "${CLAUDE_AGENT_ID:-}${CLAUDE_REVIEWER_AGENT_ID:-}${CLAUDE_ENVIRONMENT_ID:-}${CLAUDE_VAULT_ID:-}" ]; then
  echo "Nothing to tear down: no CLAUDE_* IDs in .env."
  exit 0
fi

# Sessions first. The reviewer never owns a session: it only runs as a thread
# inside the planner's sessions. A running session cannot be archived, so
# interrupt it, give it a few seconds to go idle, and try once more. If one
# still will not archive, the planner's ID stays in .env, because listing by
# that ID is the only way the next run finds the session again.
sessions_ok=1
if [ -n "${CLAUDE_AGENT_ID:-}" ]; then
  if sessions=$(ant beta:sessions list --agent-id "$CLAUDE_AGENT_ID" --max-items -1 --format jsonl --transform id --raw-output 2>/dev/null); then
    for session_id in $sessions; do
      if ! ant beta:sessions archive --session-id "$session_id" > /dev/null 2>&1; then
        ant beta:sessions:events send --session-id "$session_id" > /dev/null 2>&1 <<'YAML' || true
events:
  - type: user.interrupt
YAML
        for _ in 1 2 3 4 5 6 7 8 9 10; do
          [ "$(ant beta:sessions retrieve --session-id "$session_id" --transform status --raw-output 2>/dev/null)" = running ] || break
          sleep 2
        done
        if ! ant beta:sessions archive --session-id "$session_id" > /dev/null 2>&1; then
          echo "FAILED    session $session_id is still running" >&2; sessions_ok=0; failed=1
          continue
        fi
      fi
      echo "archived  session $session_id"
    done
  else
    echo "FAILED    could not list sessions for $CLAUDE_AGENT_ID" >&2; sessions_ok=0; failed=1
  fi
fi

if [ "$sessions_ok" -eq 1 ]; then
  archive planner   CLAUDE_AGENT_ID          beta:agents archive --agent-id "${CLAUDE_AGENT_ID:-}"
fi
archive reviewer    CLAUDE_REVIEWER_AGENT_ID beta:agents archive --agent-id "${CLAUDE_REVIEWER_AGENT_ID:-}"
archive credential  CLAUDE_NATIONAL_PARK_SERVICE_CREDENTIAL_ID beta:vaults:credentials archive --vault-id "${CLAUDE_VAULT_ID:-}" --credential-id "${CLAUDE_NATIONAL_PARK_SERVICE_CREDENTIAL_ID:-}"
archive credential  CLAUDE_WINDY_CREDENTIAL_ID                 beta:vaults:credentials archive --vault-id "${CLAUDE_VAULT_ID:-}" --credential-id "${CLAUDE_WINDY_CREDENTIAL_ID:-}"
archive vault       CLAUDE_VAULT_ID          beta:vaults archive --vault-id "${CLAUDE_VAULT_ID:-}"
archive environment CLAUDE_ENVIRONMENT_ID    beta:environments archive --environment-id "${CLAUDE_ENVIRONMENT_ID:-}"

if [ "$failed" -ne 0 ]; then
  echo "Some resources are still live and their IDs are still in .env. Run ./agents/teardown.sh again." >&2
  exit 1
fi
echo "done. The CLAUDE_* IDs are gone from .env, so ./agents/setup.sh creates new ones."
