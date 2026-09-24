#!/usr/bin/env bash
# Sign and verify a SIF image with a PGP key stored in the Apptainer keystore.
# Usage: sign_sif.sh <path-to.sif> [key-index]
#
# Pre-requisite:
#   apptainer key newpair       # generate key
#   apptainer key push          # push to keystore (optional)

set -euo pipefail

SIF="${1:-}"
KEY_IDX="${2:-0}"

if [[ -z "${SIF}" ]]; then
    echo "Usage: sign_sif.sh <path-to.sif> [key-index]" >&2
    exit 1
fi

if [[ ! -f "${SIF}" ]]; then
    echo "ERROR: SIF not found: ${SIF}" >&2
    exit 1
fi

echo "[$(date -u +%FT%TZ)] Signing ${SIF} with key index ${KEY_IDX} ..."
apptainer sign --keyidx "${KEY_IDX}" "${SIF}"

echo "[$(date -u +%FT%TZ)] Verifying signature ..."
apptainer verify "${SIF}"

echo "[$(date -u +%FT%TZ)] SIF signed and verified: ${SIF}"
