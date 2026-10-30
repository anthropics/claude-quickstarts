#!/usr/bin/env bash
# Checks, on this host, that OpenShell enforces what the proofs assume. A proof
# says a policy allows no more than the ceiling. It says nothing about whether
# the sandbox holds the policy's line, and that depends on the host: an egress
# proxy that intercepts TLS, for one, leaves OpenShell no requests to inspect.
#
# Makes one sandbox with one rule (curl may read CHECK_URL's host), sends four
# requests from inside it, and reads OpenShell's own decisions from its log.
# Needs the gateway and the sandbox image; no Managed Agents session, no API key.
# Run it after installing or upgrading OpenShell.
set -euo pipefail
cd "$(dirname "$0")/.."
agentpolicy="${AGENTPOLICY:-agentpolicy}"
url="${CHECK_URL:-https://example.com/}"           # answers a GET
other="${CHECK_OTHER_URL:-https://api.github.com/}"  # a host the rule does not name
image="${SANDBOX_IMAGE:-localhost/shs-openshell-policy:latest}"
name=shs-enforce-check

[[ "$url" =~ ^(https?)://([^/:]+)(:([0-9]+))?(/.*)?$ ]] || { echo "CHECK_URL must be an http(s) URL" >&2; exit 2; }
host="${BASH_REMATCH[2]}"
port="${BASH_REMATCH[4]:-$([ "${BASH_REMATCH[1]}" = https ] && echo 443 || echo 80)}"
other_host="${other#*://}"
other_host="${other_host%%[/:]*}"

tmp="$(mktemp -d)"
# shellcheck disable=SC2317,SC2329  # called by the EXIT trap (older shellcheck says SC2317)
cleanup() { openshell sandbox delete "$name" </dev/null >/dev/null 2>&1 || true; rm -rf "$tmp"; }
trap cleanup EXIT

# The base policy as a session gets it, recorded in a ledger that is thrown away.
AGENTPOLICY_STATE_DIR="$tmp" "$agentpolicy" prepare --profile "${PROFILE:-hello}" \
  --session sesn_01EnforceCheck000000000 --environment env_01EnforceCheck0000000000 --out "$tmp/base.yaml"
# network_policies is the last key agentpolicy writes, so the rule can be appended.
grep '^[a-z_]*:' "$tmp/base.yaml" | tail -1 | grep -q network_policies \
  || { echo "expected network_policies last in the prepared policy" >&2; exit 2; }
cat "$tmp/base.yaml" - > "$tmp/policy.yaml" <<YAML
  enforce_check:
    name: enforce_check
    endpoints:
      - host: $host
        port: $port
        protocol: rest
        enforcement: enforce
        access: read-only
    binaries:
      - path: /usr/bin/curl
YAML

openshell sandbox delete "$name" </dev/null >/dev/null 2>&1 || true
openshell sandbox create --name "$name" --from "$image" --policy "$tmp/policy.yaml" --label app=enforce-check \
  --detach --no-tty -- sleep infinity </dev/null >/dev/null
for _ in {1..150}; do [ "$(openshell sandbox get "$name" -o json </dev/null | jq -r .phase)" = Ready ] && break; sleep 0.2; done

inside() { openshell sandbox exec --name "$name" --no-tty --no-login-shell -- "$@" </dev/null >/dev/null 2>&1 || true; }
inside curl -s -m 15 "$url"
inside curl -s -m 15 -X POST -d x "$url"
inside curl -s -m 15 "$other"
inside sh -c "cp /usr/bin/curl /tmp/not-curl && /tmp/not-curl -s -m 15 '$url'"
sleep 3
openshell logs "$name" </dev/null > "$tmp/log" 2>&1

failed=0
expect() {  # what it shows, then the pattern OpenShell's log must hold
  if grep -Eq "$2" "$tmp/log"; then echo "ok      $1"; else echo "MISSING $1"; failed=1; fi
}
expect "a read the rule allows is allowed, request by request" "HTTP:GET .* ALLOWED GET .*${host}.*engine:l7"
expect "a write to the same host is denied"                    "HTTP:POST .* DENIED POST .*${host}"
expect "a host no rule names is denied"                        "NET:OPEN .* DENIED /usr/bin/curl.* -> ${other_host}:"
expect "a program the rule does not list is denied"            "NET:OPEN .* DENIED /tmp/not-curl.* -> ${host}:${port}"
if [ "$failed" = 1 ]; then
  echo "OpenShell did not log every decision above. What it did log for these hosts:" >&2
  grep -E "NET:|HTTP:" "$tmp/log" | tail -12 >&2
  echo "With no HTTP: lines at all, something between the sandbox and ${host} ends TLS first, and method and path limits are not enforced on this host." >&2
fi
exit "$failed"
