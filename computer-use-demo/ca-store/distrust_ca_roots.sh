#!/bin/bash
# Takes the CA roots listed below out of the system's CA store.
# Run as root while the image is built. Fails if a listed root is left.
set -euo pipefail
shopt -s inherit_errexit

# SHA-256 fingerprints of the certificates to take out: lowercase, no colons
DISTRUSTED="
125609aa301da0a249b97a8239cb6a34216f44dcac9f3954b14292f2e8c8608f
40f6af0346a99aa1cd1d555a4e9cce62c7f9634603ee406615833dc8c8d00367
86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b
bc4d809b15189d78db3e1d8cf4f9726a795da1643ca5f1358e1ddb0edc0d7eb3
"

CONF=/etc/ca-certificates.conf
SOURCE_DIR=/usr/share/ca-certificates
STORE_DIR=/etc/ssl/certs
BUNDLE=$STORE_DIR/ca-certificates.crt
BEGIN='-----BEGIN CERTIFICATE-----'

fail() {
    echo "$0: $1" >&2
    exit 1
}

# Prints the fingerprint of every certificate in the PEM file $1
fingerprints() {
    local found
    [ -r "$1" ] || fail "cannot read $1"
    found=$(awk -v cmd='openssl x509 -noout -fingerprint -sha256' '
        /-----BEGIN CERTIFICATE-----/ { cert = "" }
        { cert = cert $0 "\n" }
        /-----END CERTIFICATE-----/ { printf "%s", cert | cmd; close(cmd) }
    ' "$1" | sed 's/.*=//; s/://g' | tr 'A-F' 'a-f')
    [ "$(wc -w <<<"$found")" -eq "$(grep -c -e "$BEGIN" "$1" || true)" ] ||
        fail "could not read every certificate in $1"
    echo "$found"
}

# Succeeds if one of the fingerprints in $1 is listed
listed() {
    local fingerprint
    for fingerprint in $1; do
        [[ $DISTRUSTED != *"$fingerprint"* ]] || return 0
    done
    return 1
}

for entry in $DISTRUSTED; do
    [[ $entry =~ ^[0-9a-f]{64}$ ]] || fail "not a SHA-256 fingerprint: $entry"
done
before=$(grep -c -e "$BEGIN" "$BUNDLE")

# A leading "!" is how ca-certificates.conf marks a certificate as not trusted
new_conf=$(mktemp)
while IFS= read -r line || [ -n "$line" ]; do
    if [[ -n $line && $line != [#!]* ]]; then
        found=$(fingerprints "$SOURCE_DIR/$line")
        if listed "$found"; then line="!$line"; fi
    fi
    printf '%s\n' "$line"
done <"$CONF" >"$new_conf"
cat "$new_conf" >"$CONF"
rm "$new_conf"
update-ca-certificates

files=$(find "$STORE_DIR" ! -type d -exec readlink -f {} + | sort -u)
while IFS= read -r file; do
    found=$(fingerprints "$file")
    if listed "$found"; then fail "a listed root is still in $file"; fi
done <<<"$files"

echo "$BUNDLE: $before certificates before, $(grep -c -e "$BEGIN" "$BUNDLE") after"
