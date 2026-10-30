#!/usr/bin/env bash
# Sets up the demo's own policy workspace in state/demo and signs it with a
# local key. For a demo on one machine only: in a real deployment the policy
# owner's private key never sits beside the agents, and owners sign the
# repository's policy/ tree itself (make sign).
#
# The demo changes policy as it runs (a trusted key, ceiling signatures,
# promoted grants). All of that lands in state/demo, never in the tracked
# policy/ tree:
#   state/demo/agentpolicy.yaml   this repository's settings, pointed at the copy
#   state/demo/policy/          base.yaml, signers.yaml, and each profile's
#                               ceiling.yaml, task.md and policy.yaml
# The Makefile uses state/demo/agentpolicy.yaml whenever it exists.
#
# Run again after editing policy/: base, ceilings and task files are copied
# afresh and re-signed; signers and each profile's grown policy.yaml are kept.
# Remove state/demo to start the demo over.
set -euo pipefail
cd "$(dirname "$0")/.."
agentpolicy="${AGENTPOLICY:-agentpolicy}"
key="${KEY:-state/policy-owner.key}"
signer="${SIGNER:-policy-owner@example.com}"
demo=state/demo
mkdir -p "$(dirname "$key")" "$demo/policy/profiles"

# Settings: the repository's, with paths resolved from state/demo.
sed -e 's|^state_dir: .*|state_dir: ..|' \
    -e 's|^policy_dir: .*|policy_dir: policy|' \
    -e 's|^signers_file: .*|signers_file: policy/signers.yaml|' \
    -e 's|^project_dir: .*|project_dir: ../..|' \
    agentpolicy.yaml > "$demo/agentpolicy.yaml"
export AGENTPOLICY_CONFIG="$PWD/$demo/agentpolicy.yaml"

cp policy/base.yaml "$demo/policy/base.yaml"
[ -f "$demo/policy/signers.yaml" ] || cp policy/signers.yaml "$demo/policy/signers.yaml"
for dir in policy/profiles/*/; do
  p="$(basename "$dir")"
  mkdir -p "$demo/policy/profiles/$p"
  cp "$dir/ceiling.yaml" "$dir/task.md" "$demo/policy/profiles/$p/"
  for f in policy.yaml revoked.txt; do  # promote and shrink write these in the copy
    [ -f "$demo/policy/profiles/$p/$f" ] || [ ! -f "$dir/$f" ] || cp "$dir/$f" "$demo/policy/profiles/$p/"
  done
done

# Trust the demo key in the workspace's signers file (once).
if [ -f "$key" ]; then
  entry="$("$agentpolicy" ceiling pubkey --key "$key" --identity "$signer")"
else
  entry="$("$agentpolicy" ceiling keygen --key "$key" --identity "$signer" | tail -2)"
fi
signers="$demo/policy/signers.yaml"
if ! grep -qF "$(printf '%s\n' "$entry" | tail -1)" "$signers"; then
  if grep -q '^signers: \[\]' "$signers"; then
    tmp="$(mktemp)"
    sed 's/^signers: \[\]/signers:/' "$signers" > "$tmp" && mv "$tmp" "$signers"
  fi
  printf '%s\n' "$entry" >> "$signers"
  echo "trusted $signer in $signers (a demo key, outside the tracked policy/ tree)"
fi

for dir in "$demo"/policy/profiles/*/; do
  "$agentpolicy" ceiling sign --profile "$(basename "$dir")" --key "$key" --identity "$signer"
done
