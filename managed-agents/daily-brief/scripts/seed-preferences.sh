#!/usr/bin/env bash
# Writes preferences.md into the read-only `preferences` memory store.
# `ant apply` creates the store but never its contents, so this is how your rules get in.
# Usage: scripts/seed-preferences.sh [file]   (default: preferences.md, your copy of preferences.example.md)
set -euo pipefail

cd "$(dirname "$0")/.."
FILE="${1:-preferences.md}"

# A typo'd path would otherwise write an empty preferences.md over a working one.
[ -s "$FILE" ] || { echo "$FILE does not exist or is empty; nothing written" >&2; exit 1; }

STORE_ID=$(jq -r '.resources["./agents/daily-brief/memory_store_preferences.yaml"].id // empty' claude-lock.json 2>/dev/null || true)
[ -n "$STORE_ID" ] || { echo "could not find the preferences store id in claude-lock.json; run 'ant apply agents/daily-brief/deployment.md' first" >&2; exit 1; }

EXISTING=$(ant beta:memory-stores:memories list --memory-store-id "$STORE_ID" --path-prefix / \
  --transform '{id,path}' --format jsonl | jq -r 'select(.path == "/preferences.md") | .id' | head -1)

if [ -n "$EXISTING" ]; then
  ant beta:memory-stores:memories update --memory-id "$EXISTING" --memory-store-id "$STORE_ID" \
    --content "$(cat "$FILE")" --transform id -r
else
  ant beta:memory-stores:memories create --memory-store-id "$STORE_ID" --path /preferences.md \
    --content "$(cat "$FILE")" --transform id -r
fi
