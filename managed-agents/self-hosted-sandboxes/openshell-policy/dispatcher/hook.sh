#!/usr/bin/env bash
# ON_WORK_HOOK for ../openshell/on-work.sh: the decisions that quickstart
# leaves to a hook, made by agentpolicy.
#
#   admit          Takes the session's profile from the operator's map of
#                  environments (`agentpolicy environment set`), never from the
#                  session or its agent; reads the session's agent with the
#                  session token on stdin; refuses a session a stop covers.
#                  Prints the sandbox's labels.
#   policy <out>   Writes a starting policy proved inside the profile's signed
#                  ceiling, or nothing (no trusted ceiling, no proof: no
#                  sandbox).
#   verify <file>  Proves an existing sandbox's policy inside the ceiling as
#                  it is now: 0 use it, 1 replace it, 2 refuse the session.
#   start          Checks for a stop once more, just before the worker runs.
#
# on-work.sh passes the poller's IDs, already checked, and the labels `admit`
# printed in ON_WORK_LABELS. The environment key is already gone.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
AGENTPOLICY="${AGENTPOLICY:-agentpolicy}"
export AGENTPOLICY_CONFIG="${AGENTPOLICY_CONFIG:-$here/../agentpolicy.yaml}"

: "${ANTHROPIC_SESSION_ID:?}" "${ANTHROPIC_ENVIRONMENT_ID:?}"

label() { sed -n "s/^$1=//p" <<<"${ON_WORK_LABELS:-}" | head -n 1; }
say() { echo "[hook] session=${ANTHROPIC_SESSION_ID} $*" >&2; }

# A stopped session, agent, environment or profile gets no worker. Anything
# but a clear "not stopped" (exit 0) refuses too.
refuse_if_stopped() {
  local rc=0 why
  why="$("$AGENTPOLICY" stopped --session "$ANTHROPIC_SESSION_ID" --agent "$1" \
    --environment "$ANTHROPIC_ENVIRONMENT_ID" --profile "$2")" || rc=$?
  case "$rc" in
    0) ;;
    3) say "${why}; refusing"; exit 1 ;;
    *) say "could not check for a stop; refusing"; exit 1 ;;
  esac
}

ids=(--profile "$(label profile)" --session "$ANTHROPIC_SESSION_ID"
     --environment "$ANTHROPIC_ENVIRONMENT_ID" --agent "$(label agent)" --agent-version "$(label agent_version)")

case "${1:-}" in
  admit)
    # The session token waits on stdin for session-identity below.
    profile="$("$AGENTPOLICY" environment get "$ANTHROPIC_ENVIRONMENT_ID" </dev/null)" \
      || { say "no profile for environment ${ANTHROPIC_ENVIRONMENT_ID}; refusing"; exit 1; }
    [[ "$profile" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || { say "malformed profile ${profile}; refusing"; exit 1; }
    : "${ANTHROPIC_BASE_URL:?the API as this host reaches it}"
    identity="$("$AGENTPOLICY" session-identity --base-url "$ANTHROPIC_BASE_URL" --session "$ANTHROPIC_SESSION_ID" --profile "$profile")" \
      || { say "the session's agent could not be read or is not admitted on profile ${profile}; refusing"; exit 1; }
    agent_id="$(jq -r '.agent_id // ""' <<<"$identity")"
    agent_version="$(jq -r '.agent_version // ""' <<<"$identity")"
    [[ "$agent_id" =~ ^agent_[A-Za-z0-9]+$ ]] || { say "malformed agent id ${agent_id}; refusing"; exit 1; }
    [[ -z "$agent_version" || "$agent_version" =~ ^[A-Za-z0-9._-]{1,63}$ ]] \
      || { say "malformed agent version ${agent_version}; refusing"; exit 1; }
    refuse_if_stopped "$agent_id" "$profile"
    say "agent=${agent_id}${agent_version:+@$agent_version} env=${ANTHROPIC_ENVIRONMENT_ID} profile=${profile}"
    printf 'environment=%s\nprofile=%s\nagent=%s\n' "$ANTHROPIC_ENVIRONMENT_ID" "$profile" "$agent_id"
    [ -z "$agent_version" ] || printf 'agent_version=%s\n' "$agent_version"
    ;;
  policy)
    out="${2:?policy needs an output file}"
    "$AGENTPOLICY" prepare "${ids[@]}" --out "$out"
    ;;
  verify)
    current="${2:?verify needs the current policy file}"
    rc=0
    "$AGENTPOLICY" verify-sandbox "${ids[@]}" --policy "$current" || rc=$?
    # on-work.sh deletes the sandbox on 1, so only agentpolicy's own "replace
    # it" becomes 1. A crash, which also exits 1, refuses the session instead.
    case "$rc" in 0) exit 0 ;; 4) exit 1 ;; *) exit 2 ;; esac
    ;;
  start)
    refuse_if_stopped "$(label agent)" "$(label profile)"
    ;;
  *)
    echo "usage: $0 admit|policy <out>|verify <file>|start" >&2
    exit 2
    ;;
esac
