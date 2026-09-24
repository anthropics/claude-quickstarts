#!/usr/bin/env bash
# Build AGI_Core_Env.sif from definition file.
# Requires: apptainer >= 1.2 with fakeroot support configured.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEF="${SCRIPT_DIR}/AGI_Core_Env.def"
SIF="${SCRIPT_DIR}/AGI_Core_Env.sif"

if [[ ! -f "${DEF}" ]]; then
    echo "ERROR: Definition file not found: ${DEF}" >&2
    exit 1
fi

echo "[$(date -u +%FT%TZ)] Building ${SIF} ..."
apptainer build --fakeroot "${SIF}" "${DEF}"

echo "[$(date -u +%FT%TZ)] Build complete: ${SIF}"
ls -lh "${SIF}"
