#!/usr/bin/env bash
# Start one run now, wait for it, and print the agent's last message and the run
# record it wrote. Works while the deployment is paused, so use it to test.
set -euo pipefail
cd "$(dirname "$0")/.."

# The agent's text can echo what it read in Slack, and that can carry terminal
# escape sequences. Print it as plain text: drop C0 and C1 control characters
# (except tab and newline) at the code-point level, so UTF-8 encoded ones go too.
plain() { perl -CS -pe 's/[\x00-\x08\x0b-\x1f\x7f-\x9f]//g'; }

DEPLOYMENT_ID=$(jq -r '.resources["./agents/daily-brief/deployment.md"].id // empty' claude-lock.json 2>/dev/null || true)
STATE_ID=$(jq -r '.resources["./agents/daily-brief/memory_store_state.yaml"].id // empty' claude-lock.json 2>/dev/null || true)
[ -n "$DEPLOYMENT_ID" ] || { echo "run agents/setup.sh first" >&2; exit 1; }

RUN=$(ant beta:deployments run --deployment-id "$DEPLOYMENT_ID" --format json)
SESSION_ID=$(echo "$RUN" | jq -r '.session_id // empty')
if [ -z "$SESSION_ID" ]; then
  echo "the run did not start a session:" >&2
  echo "$RUN" | jq '.error' >&2
  exit 1
fi
echo "session $SESSION_ID started; a run takes one to three minutes"
echo "watch it live: ant beta:sessions connect $SESSION_ID"

status=running
for _ in $(seq 1 90); do
  sleep 10
  status=$(ant beta:sessions retrieve --session-id "$SESSION_ID" --transform status --raw-output)
  case "$status" in idle | terminated) break ;; esac
done

echo
echo "== status: $status, cost: \$$(ant beta:sessions retrieve --session-id "$SESSION_ID" --transform usage.list_cost.amount --raw-output | awk '{printf "%.2f", $1/100}')"
echo "== errors logged by the session (an unreadable source shows up here):"
ant beta:sessions:events list --session-id "$SESSION_ID" --order asc --format jsonl \
  --transform '{type,error}' | jq -r 'select(.type == "session.error") | "  \(.error.type): \(.error.message // "")"' | sort -u | plain
echo "== the agent's last message:"
ant beta:sessions:events list --session-id "$SESSION_ID" --order desc --format jsonl \
  --transform '{type,"text":content.#(type=="text")#.text}' | jq -rs '[.[] | select(.type == "agent.message")][0].text // ["(none)"] | join("\n")' | plain
echo "== run records in the state store:"
ant beta:memory-stores:memories list --memory-store-id "$STATE_ID" --path-prefix /runs/ --format jsonl --transform path | jq -r . | plain || true
