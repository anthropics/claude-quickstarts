#!/usr/bin/env bash
# Archive everything ./agents/setup.sh created, plus any sessions started from
# the UI: each resource `ant apply` recorded in claude-lock.json, dropping its
# entry once it is archived, and the lockfile itself when nothing is left, so
# the next ./agents/setup.sh starts from scratch. Archive, not delete: the
# event logs stay readable in the Console. Archiving the vault discards the
# two vendor keys with it.
#
# Safe to re-run. An entry stays in claude-lock.json only while its archive
# keeps failing, so fix the cause and run this again.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

command -v jq >/dev/null || { echo "jq not found on PATH (see the README)" >&2; exit 1; }
if [ -f .env ]; then set -a; . ./.env; set +a; fi

failed=0
lock_id() { [ -f claude-lock.json ] && jq -r --arg f "$1" '.resources[$f].id // empty' claude-lock.json; }
forget() { jq --arg f "$1" 'del(.resources[$f])' claude-lock.json > claude-lock.json.tmp && mv claude-lock.json.tmp claude-lock.json; }

# archive <label> <lockfile key> <ant args...>: archive one resource, and drop
# its entry only when that worked or the API says it is already archived or gone.
archive() {
  local label=$1 key=$2 id; id=$(lock_id "$2"); shift 2
  [ -n "$id" ] || return 0
  local out
  if out=$(ant "$@" "$id" </dev/null 2>&1 > /dev/null); then
    echo "archived  $label $id"; forget "$key"
  elif grep -qiE 'already archived|not[ _]found|404' <<<"$out"; then
    echo "gone      $label $id"; forget "$key"
  else
    echo "FAILED    $label $id: $(tail -n 1 <<<"$out" | cut -c1-160)" >&2; failed=1
  fi
}

planner=$(lock_id ./agents/roadtrip-planner.md)
if [ ! -f claude-lock.json ] || [ "$(jq '.resources | length' claude-lock.json)" = 0 ]; then
  echo "Nothing to tear down: no claude-lock.json here, or no resources in it."
  exit 0
fi

# Sessions first. The reviewer never owns a session: it only runs as a thread
# inside the planner's sessions. A running session cannot be archived, so
# interrupt it, give it a few seconds to go idle, and try once more. If one
# still will not archive, the planner's entry stays in the lockfile, because
# listing by that ID is the only way the next run finds the session again.
sessions_ok=1
if [ -n "$planner" ]; then
  if sessions=$(ant beta:sessions list --agent-id "$planner" --max-items -1 --format jsonl --transform id --raw-output </dev/null 2>/dev/null); then
    for session_id in $sessions; do
      if ! ant beta:sessions archive --session-id "$session_id" </dev/null > /dev/null 2>&1; then
        ant beta:sessions:events send --session-id "$session_id" > /dev/null 2>&1 <<'YAML' || true
events:
  - type: user.interrupt
YAML
        for _ in 1 2 3 4 5 6 7 8 9 10; do
          [ "$(ant beta:sessions retrieve --session-id "$session_id" --transform status --raw-output </dev/null 2>/dev/null)" = running ] || break
          sleep 2
        done
        if ! ant beta:sessions archive --session-id "$session_id" </dev/null > /dev/null 2>&1; then
          echo "FAILED    session $session_id is still running" >&2; sessions_ok=0; failed=1
          continue
        fi
      fi
      echo "archived  session $session_id"
    done
  else
    echo "FAILED    could not list sessions for $planner" >&2; sessions_ok=0; failed=1
  fi
fi

if [ "$sessions_ok" -eq 1 ]; then
  archive planner   ./agents/roadtrip-planner.md        beta:agents archive --agent-id
fi
archive reviewer    ./agents/plan-reviewer.md           beta:agents archive --agent-id
# The two credentials go with their vault.
archive vault       ./vaults/roadtrip-planner.yaml      beta:vaults archive --vault-id
archive environment ./environments/roadtrip-planner.yaml beta:environments archive --environment-id

if [ "$failed" -ne 0 ]; then
  echo "Some resources are still live and their entries are still in claude-lock.json. Run ./agents/teardown.sh again." >&2
  exit 1
fi
if [ "$(jq '.resources | length' claude-lock.json)" = 0 ]; then
  rm -f claude-lock.json
  echo "done. claude-lock.json is gone, so ./agents/setup.sh creates new resources."
else
  echo "done, but claude-lock.json still lists resources this script does not remove:"
  jq -r '.resources | to_entries[] | "  \(.value.id)  (\(.key), \(.value.kind))"' claude-lock.json
fi
