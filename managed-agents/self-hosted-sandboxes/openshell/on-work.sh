#!/usr/bin/env bash
# Invoked by `ant beta:worker poll --on-work` once per claimed work item.
#
# The poller passes ANTHROPIC_{WORK,ENVIRONMENT,SESSION}_ID and
# ANTHROPIC_ENVIRONMENT_KEY in the environment and the work item JSON on
# stdin. This script is where the credentials split: it takes the session
# token out of that JSON and pipes it to `ant beta:worker run` inside the
# session's OpenShell sandbox. The environment key stops here, on the host.
#
# The sandbox belongs to the session, not to the work item. The first work
# item creates it, this script stops it when the worker exits, and a later
# work item for the same session starts it again with /workspace intact.
#
# This script waits for the worker: the poller stops a work item as soon as
# this script returns, so it stays until the worker idles out and exits. One
# poller therefore serves one session at a time, and the worker's log streams
# into the poller's output.
set -euo pipefail

: "${ANTHROPIC_SESSION_ID:?on-work: ANTHROPIC_SESSION_ID not set by poller}"
: "${ANTHROPIC_ENVIRONMENT_ID:?on-work: ANTHROPIC_ENVIRONMENT_ID not set by poller}"
: "${ANTHROPIC_WORK_ID:?on-work: ANTHROPIC_WORK_ID not set by poller}"

# This script does not need the environment key. Unset it so that no child
# process inherits it. `secret` goes too: a variable that arrives exported
# stays exported when it is assigned, and would hand the token to every child.
unset ANTHROPIC_ENVIRONMENT_KEY secret

# The work JSON is on stdin. Its `secret` is URL-safe base64 JSON that bundles
# the session token with other tokens the worker does not use. Only that one
# goes into the sandbox, re-wrapped the same way. With no usable token in the
# payload, `secret` ends up empty.
secret="$(jq -r '
  (.secret // "") | gsub("-"; "+") | gsub("_"; "/") | (try @base64d catch "")
  | (fromjson? // {}) | .sessions_token // "" | select(. != "")
  | {sessions_token: .} | @base64 | gsub("\\+"; "-") | gsub("/"; "_")
')"

# The IDs become a sandbox name, policy paths, and command arguments, so check
# their shape.
for id in "$ANTHROPIC_SESSION_ID" "$ANTHROPIC_ENVIRONMENT_ID" "$ANTHROPIC_WORK_ID"; do
  [[ "$id" =~ ^(sesn|env|work)_[A-Za-z0-9]+$ ]] || { echo "[on-work] refusing malformed id: ${id}" >&2; exit 1; }
done

# An empty value means the item carried no session token, and this demo never
# hands the environment key to a sandbox, so the worker would have no
# credential at all. Fail the item loudly (the poller stops it when this
# script returns).
if [ -z "$secret" ]; then
  echo "[on-work] work=${ANTHROPIC_WORK_ID} carried no per-session secret: this environment does not issue them, use ../docker instead" >&2
  exit 1
fi

IMAGE="${SANDBOX_IMAGE:-shs-openshell}"
# OpenShell names are at most 19 characters of [a-z0-9-], too short for a
# session ID. Use its last 15 characters and keep the whole ID as a label.
NAME="shs-$(printf %s "$ANTHROPIC_SESSION_ID" | tr '[:upper:]' '[:lower:]' | tail -c 15)"
phase() { openshell sandbox get "$NAME" -o json 2>/dev/null | jq -r '.phase // empty'; }

# Once this script owns the sandbox, the EXIT trap stops the sandbox however
# the script ends. Stopping kills every process inside and keeps /workspace.
# The agent runs as the same user as `sleep infinity` and can kill it, which
# puts the sandbox in Error. In OpenShell 0.1.2 both `stop` and `start` then
# fail and what the agent started keeps running, so delete the sandbox instead.
owned=
policy=
# shellcheck disable=SC2329  # called by the EXIT trap
cleanup() {
  # A signal that lands here would end cleanup early, and Ctrl-C would also kill
  # the `sandbox stop` below. Children inherit an ignored signal.
  trap '' TERM INT
  [ -z "$policy" ] || rm -f "$policy"
  [ -n "$owned" ] || return 0
  # Ctrl-C also kills a `sandbox create` in progress, but the gateway carries on
  # provisioning, and it refuses to stop a sandbox until that is done. Wait at
  # most 20s: the poller kills this script 30s after it asks it to stop.
  for _ in {1..100}; do [ "$(phase)" = Provisioning ] || break; sleep 0.2; done
  openshell sandbox stop "$NAME" >/dev/null 2>&1 && return 0
  if [ "$(phase)" = Error ]; then
    echo "[on-work] ${NAME} is in Error and cannot be stopped: deleting it, /workspace included" >&2
    openshell sandbox delete "$NAME" >/dev/null 2>&1 || true
  elif [ -n "$(phase)" ]; then
    echo "[on-work] could not stop ${NAME}: check it with \`openshell sandbox get ${NAME}\`" >&2
  fi
}
trap cleanup EXIT
# Ctrl-C reaches this script twice, as SIGINT from the terminal and as SIGTERM
# from the poller. The first signal turns both off so the second cannot end
# cleanup before it has stopped the sandbox.
trap 'trap "" TERM INT; exit 143' TERM INT

# The same for a sandbox left in Error by a run that never reached its cleanup.
# `sandbox delete` can return before the sandbox is gone. Wait at most 20s. If
# it is still there, `sandbox start` refuses it and this work item fails.
if [ "$(phase)" = Error ]; then
  echo "[on-work] session=${ANTHROPIC_SESSION_ID} sandbox=${NAME} is in Error, deleting it" >&2
  openshell sandbox delete "$NAME" >&2
  for _ in {1..100}; do [ -n "$(phase)" ] || break; sleep 0.2; done
fi

case "$(phase)" in
  "")
    echo "[on-work] session=${ANTHROPIC_SESSION_ID} work=${ANTHROPIC_WORK_ID} sandbox=${NAME} (creating)" >&2
    owned=1
    # Tie the sandbox to its session. With a wildcard where the IDs go, code in
    # the sandbox could use the same routes on any other session it had a
    # credential for, including one in someone else's organization.
    policy="$(mktemp)"
    sed -e "s/SESSION_ID/${ANTHROPIC_SESSION_ID}/" \
      -e "s/ENVIRONMENT_ID/${ANTHROPIC_ENVIRONMENT_ID}/" \
      "$(dirname "$0")/policy.yaml" > "$policy"
    # `sleep infinity` is the sandbox's main process and only holds it open.
    # The worker cannot be the main process, because OpenShell reruns that
    # command on `sandbox start` and each work item has its own token.
    # SANDBOX_CREATE_ARGS adds `sandbox create` flags (--cpu, --memory).
    # shellcheck disable=SC2086
    openshell sandbox create \
      --name "$NAME" \
      --from "$IMAGE" \
      --policy "$policy" \
      --label app=shs-openshell \
      --label "session=${ANTHROPIC_SESSION_ID}" \
      --detach \
      --no-tty \
      ${SANDBOX_CREATE_ARGS:-} \
      -- sleep infinity >&2 || {
      # A create the gateway accepted and then failed (an image it cannot pull)
      # leaves a sandbox in Error for cleanup to delete. Any other failure (a
      # second poller won the race for the name) leaves nothing of ours.
      [ "$(phase)" = Error ] || owned=
      exit 1
    }
    ;;
  Ready)
    # A duplicate work item for a session another poller on this host is
    # already serving: leave that worker alone. A running sandbox with no
    # worker in it was left behind by a killed on-work.sh, and is reused.
    # (`sandbox exec` reads its stdin to the end before it sends the command.)
    if openshell sandbox exec --name "$NAME" --no-tty --no-login-shell -- pgrep -x ant </dev/null >/dev/null 2>&1; then
      echo "[on-work] session=${ANTHROPIC_SESSION_ID} already has a live worker in ${NAME}; skipping" >&2
      exit 0
    fi
    echo "[on-work] session=${ANTHROPIC_SESSION_ID} work=${ANTHROPIC_WORK_ID} sandbox=${NAME} (reusing)" >&2
    owned=1
    ;;
  Provisioning|Starting)
    # The same duplicate, a moment earlier: the other poller is still bringing
    # the sandbox up. It is not ours to start, and not ours to stop.
    echo "[on-work] session=${ANTHROPIC_SESSION_ID} another poller is starting ${NAME}; skipping" >&2
    exit 0
    ;;
  *)
    echo "[on-work] session=${ANTHROPIC_SESSION_ID} work=${ANTHROPIC_WORK_ID} sandbox=${NAME} (restarting)" >&2
    owned=1
    openshell sandbox start "$NAME" >&2
    ;;
esac

# The token travels on stdin and nowhere else. `sandbox exec` hands its own
# stdin to the command as a pipe, and the worker reads that pipe once at
# startup. So the token is never in a file, on a command line, in the
# sandbox definition the gateway stores, or in the worker's environment.
# printf is a shell builtin, so the token is not in the host's process table
# either. It is still in the worker's memory, and the agent runs as the same
# user, so assume the agent can read it. The IDs are not secrets.
#
# --no-login-shell matters: $HOME is /workspace, which the agent writes and
# which outlives the work item. A login shell would run the agent's .profile
# with the next work item's token waiting on stdin.
#
# The poller sends SIGTERM to this script alone when it shuts down, and bash
# runs a trap only between commands, so the worker runs in the background
# under `wait`.
printf %s "$secret" | openshell sandbox exec \
  --name "$NAME" \
  --no-tty \
  --no-login-shell \
  --env "ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://api.anthropic.com}" \
  --env "ANTHROPIC_SESSION_ID=${ANTHROPIC_SESSION_ID}" \
  --env "ANTHROPIC_ENVIRONMENT_ID=${ANTHROPIC_ENVIRONMENT_ID}" \
  --env "ANTHROPIC_WORK_ID=${ANTHROPIC_WORK_ID}" \
  -- /usr/local/bin/ant beta:worker run \
    --work-secret-file /dev/stdin \
    --workdir /workspace \
    --max-idle 60s \
    --log-format text &
unset secret

# The worker owns the session from here (lease heartbeat, event stream, tool
# dispatch, force-stop when it idles out).
rc=0
wait $! || rc=$?
echo "[on-work] session=${ANTHROPIC_SESSION_ID} worker exited rc=${rc}, stopping ${NAME}" >&2
exit "$rc"
