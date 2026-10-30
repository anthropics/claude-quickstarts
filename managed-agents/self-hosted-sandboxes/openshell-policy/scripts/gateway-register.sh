#!/usr/bin/env bash
# Registers the containerized gateway (stack/openshell) with the OpenShell CLI
# that scripts/ops runs, the way `openshell gateway add` would: an entry under
# state/openshell/config/openshell/gateways/<name>/ with the endpoint and the
# client certificate, marked active. agentpolicy reads the same entry.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
name="${OPENSHELL_GATEWAY_NAME:-openshell-policy}"
port="${OPENSHELL_GATEWAY_PORT:-18670}"
pki="$root/state/openshell/pki"
cfg="$root/state/openshell/config/openshell"
[ -f "$pki/client/tls.crt" ] || { echo "no $pki: run make pki" >&2; exit 1; }

umask 077
mkdir -p "$cfg/gateways/$name/mtls"
cp "$pki/ca.crt" "$cfg/gateways/$name/mtls/ca.crt"
cp "$pki/client/tls.crt" "$cfg/gateways/$name/mtls/tls.crt"
cp "$pki/client/tls.key" "$cfg/gateways/$name/mtls/tls.key"
jq -n --arg name "$name" --argjson port "$port" \
  '{name: $name, gateway_endpoint: "https://127.0.0.1:\($port)", is_remote: false, gateway_port: $port}' \
  > "$cfg/gateways/$name/metadata.json"
printf '%s\n' "$name" > "$cfg/active_gateway"
echo "registered gateway $name at https://127.0.0.1:$port"
