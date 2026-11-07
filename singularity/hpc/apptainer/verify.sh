#!/usr/bin/env bash
# Verify PGP signature on a SIF image before execution.
# Usage: verify.sh <path-to.sif>
set -euo pipefail

SIF="${1:-}"

if [[ -z "${SIF}" ]]; then
    echo "Usage: verify.sh <path-to.sif>" >&2
    exit 1
fi

if [[ ! -f "${SIF}" ]]; then
    echo "ERROR: SIF not found: ${SIF}" >&2
    exit 1
fi

echo "[$(date -u +%FT%TZ)] Verifying signature: ${SIF}"
apptainer verify "${SIF}"
echo "[$(date -u +%FT%TZ)] Signature OK — image trusted."
