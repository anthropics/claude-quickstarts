#!/usr/bin/env bash
# Deletes every memory in the `state` store: bookmarks, ledger, notes, proposals, run records.
# Use it after test runs, so the first real run starts clean. Each deletion leaves a version
# behind in the store's audit trail. Pass --yes to skip the prompt.
set -euo pipefail

cd "$(dirname "$0")/.."
STORE_ID=$(jq -r '.resources["./agents/daily-brief/memory_store_state.yaml"].id // empty' claude-lock.json 2>/dev/null || true)
[ -n "$STORE_ID" ] || { echo "could not find the state store id in claude-lock.json; run 'ant apply agents/daily-brief/deployment.md' first" >&2; exit 1; }

# Paths were written by the agent, so print them as plain text (no control characters).
IDS=$(ant beta:memory-stores:memories list --memory-store-id "$STORE_ID" --path-prefix / \
  --transform '{id,path,type}' --format jsonl | jq -r 'select(.type == "memory") | "\(.id) \(.path)"' | perl -CS -pe 's/[\x00-\x08\x0b-\x1f\x7f-\x9f]//g')

if [ -z "$IDS" ]; then
  echo "state store is already empty"
  exit 0
fi

echo "$IDS"
if [ "${1:-}" != "--yes" ]; then
  read -r -p "Delete these from $STORE_ID? [y/N] " answer
  [ "$answer" = "y" ] || { echo "aborted"; exit 1; }
fi

echo "$IDS" | while read -r id path; do
  # stdin from /dev/null: ant would otherwise swallow the rest of the list piped into this loop.
  ant beta:memory-stores:memories delete --memory-id "$id" --memory-store-id "$STORE_ID" </dev/null >/dev/null
  echo "deleted $path"
done
