#!/usr/bin/env bash
# The hello-world loop: grow, promote, and check the result, on the "hello"
# profile, whose ceiling allows curl to read example.com and nothing else.
#
# Needs, each in its own terminal and left running:
#   make dispatcher   (sandboxes for sessions)
#   make reviewer     (decides proposals)
#   make audit        (collects the evidence promote and shrink use)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$here/../.."
# Sessions are created with your own credentials: `ant auth login`, or
# ANTHROPIC_API_KEY, which the SDK finds itself.
base_url="${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"
agentpolicy="${AGENTPOLICY:-agentpolicy}"

step() { printf '\n=== %s\n' "$*"; }

step "1. A new agent starts with the base policy only. It asks for what it needs."
"$agentpolicy" status --profile hello
sid_file="$(mktemp)"
"$agentpolicy" agents run --base-url "$base_url" --session-id-file "$sid_file" \
  "Fetch https://example.com/ with curl and tell me the page title. Then fetch https://api.github.com/zen with curl and tell me what it says."
session="$(cat "$sid_file")"

# The audit collector writes a session's allowed decisions as they happen.
# Promotion needs them.
printf 'waiting for %s audit log' "$session"
for _ in $(seq 1 120); do
  compgen -G "$root/state/ocsf/hello/${session}-*.jsonl" >/dev/null && break
  printf .
  sleep 2
done
echo
compgen -G "$root/state/ocsf/hello/${session}-*.jsonl" >/dev/null \
  || { echo "no audit log for $session yet; is make audit running?" >&2; exit 1; }

step "2. What the reviewer decided (expect example.com approved, api.github.com rejected as outside the ceiling)"
jq -r 'select(.kind=="decision" and .profile=="hello" and .code!="gateway_draft") | "\(.ts)  \(.action)  \(.rule_name)  \(.code)"' "$root/state/ledger.jsonl" | tail -5

step "3. Promote: the approved grant the session used becomes a starting grant"
echo "The diff a person would read, and merge:"
"$agentpolicy" promote --profile hello
echo
echo "The demo applies it:"
"$agentpolicy" promote --profile hello --apply

step "4. A second session needs no proposal: example.com is in its starting policy"
asked() { grep '"kind": "decision"' "$root/state/ledger.jsonl" | grep -vc gateway_draft || true; }
before="$(asked)"
"$agentpolicy" agents run --base-url "$base_url" \
  "Fetch https://example.com/ with curl and tell me the page title."
after="$(asked)"
echo "reviewer decisions during step 4: $((after - before)) (expect 0)"

step "5. Shrink (dry run): starting grants no session used in the window would be removed"
"$agentpolicy" shrink --profile hello --window-days 1 --allow-short-evidence || true
echo
echo "To see a removal, wait out a window with no use and run: make shrink APPLY=1"
