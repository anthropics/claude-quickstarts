#!/usr/bin/env bash
# Provision this quickstart. `ant apply` creates or updates the environment,
# the vault, the reviewer, and the planner (whose roster names the reviewer's
# file, so apply creates the reviewer first and pins the planner to its
# version) and records their IDs in claude-lock.json, which the app reads.
# Then the one step apply leaves to you, because no secret passes through it:
# the two vendor keys go into the vault as credentials. Re-run after editing a
# file: apply publishes the change as a new agent version that new trips pick
# up. Live credentials are left alone, so a flip from README step 2 survives.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v jq >/dev/null || { echo "jq not found on PATH (see the README)" >&2; exit 1; }
# .env holds two API keys, so keep it owner-only.
umask 077
[ -f .env ] || cp .env.example .env
chmod 600 .env
set -a; . ./.env; set +a

# The two keys are interpolated into a YAML body below. A quote or newline in
# one would change that body, so refuse anything that is not a plain token.
for v in NATIONAL_PARK_SERVICE_API_KEY WINDY_API_KEY; do
  [ -n "${!v:-}" ] || { echo "$v is not set in .env (see .env.example)" >&2; exit 1; }
  [[ "${!v}" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "$v has characters an API key should not. Check for quotes or spaces in .env." >&2; exit 1; }
done

# --yes: the plan is four small resources and this script is the review. Run
# `ant apply --dry-run agents environments vaults` first to see it.
ant apply --yes agents environments vaults

vault=$(jq -r '.resources["./vaults/roadtrip-planner.yaml"].id // empty' claude-lock.json)
: "${vault:?claude-lock.json has no vault: read the ant apply output above}"

# Both credentials are `environment_variable` credentials: the sandbox sees
# $NATIONAL_PARK_SERVICE_API_KEY and $WINDY_API_KEY as opaque placeholders, and
# the real key is substituted into a request only when the request host is in
# the credential's allowed_hosts AND the placeholder sits somewhere
# injection_location allows. NPS wants its key in a request header and Windy
# wants it in the POST body, so each credential sets the location its vendor
# documents. Same vault, same mechanism, opposite locations.
#
# The bodies are heredocs so the keys travel on stdin. They never land in a
# YAML file and never show up in a process listing. Each credential is created
# once; the vault is the record of whether it exists. To change an
# injection_location on a live one, see README.md, step 2.
existing=$(ant beta:vaults:credentials list --vault-id "$vault" --max-items -1 --format jsonl \
  --transform auth.secret_name --raw-output </dev/null)

if grep -qx NATIONAL_PARK_SERVICE_API_KEY <<<"$existing"; then
  echo "credential: NATIONAL_PARK_SERVICE_API_KEY is already in $vault"
else
  credential=$(ant beta:vaults:credentials create --vault-id "$vault" --transform id --raw-output <<YAML
display_name: National Park Service API key (header)
metadata:
  quickstart: roadtrip-planner
  vendor: nps
auth:
  type: environment_variable
  secret_name: NATIONAL_PARK_SERVICE_API_KEY
  secret_value: "$NATIONAL_PARK_SERVICE_API_KEY"
  networking:
    type: limited
    allowed_hosts: [developer.nps.gov]
  injection_location: {header: true, body: false}
YAML
  )
  echo "credential: created $credential  NATIONAL_PARK_SERVICE_API_KEY -> developer.nps.gov (header)"
fi

if grep -qx WINDY_API_KEY <<<"$existing"; then
  echo "credential: WINDY_API_KEY is already in $vault"
else
  credential=$(ant beta:vaults:credentials create --vault-id "$vault" --transform id --raw-output <<YAML
display_name: Windy API key (body)
metadata:
  quickstart: roadtrip-planner
  vendor: windy
auth:
  type: environment_variable
  secret_name: WINDY_API_KEY
  secret_value: "$WINDY_API_KEY"
  networking:
    type: limited
    allowed_hosts: [api.windy.com]
  injection_location: {header: false, body: true}
YAML
  )
  echo "credential: created $credential  WINDY_API_KEY -> api.windy.com (body)"
fi

cat <<'DONE'

| secret                        | host              | injected in |
|-------------------------------|-------------------|-------------|
| NATIONAL_PARK_SERVICE_API_KEY | developer.nps.gov | header      |
| WINDY_API_KEY                 | api.windy.com     | body        |

Next: npm run dev  ->  http://localhost:3000
DONE
