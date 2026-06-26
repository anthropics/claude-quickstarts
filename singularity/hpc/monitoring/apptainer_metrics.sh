#!/usr/bin/env bash
# Cron script: collect Apptainer runtime metrics and write to Prometheus textfile.
# Schedule: */1 * * * * /path/to/apptainer_metrics.sh
#
# Output written to TEXTFILE_DIR (default: /var/lib/node_exporter/textfile_collector/)
# and picked up by node_exporter --collector.textfile.directory.

set -euo pipefail

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}"
OUTPUT="${TEXTFILE_DIR}/apptainer.prom"
TMP="${OUTPUT}.$$"

# ── Helpers ────────────────────────────────────────────────────────────────────

instances_running=0
if command -v apptainer &>/dev/null; then
    instances_running=$(apptainer instance list 2>/dev/null | tail -n +2 | wc -l || echo 0)
fi

sif_count=0
sif_size_bytes=0
if [[ -d "${SIF_DIR:-/share/groupname/containers}" ]]; then
    sif_count=$(find "${SIF_DIR:-/share/groupname/containers}" -name "*.sif" 2>/dev/null | wc -l)
    sif_size_bytes=$(find "${SIF_DIR:-/share/groupname/containers}" -name "*.sif" 2>/dev/null \
        -exec stat --printf="%s\n" {} \; 2>/dev/null | awk '{s+=$1} END {print s+0}')
fi

scrape_ts=$(date +%s)

# ── Write metrics ──────────────────────────────────────────────────────────────

cat > "${TMP}" <<EOF
# HELP apptainer_instances_running Number of running Apptainer instances
# TYPE apptainer_instances_running gauge
apptainer_instances_running ${instances_running}

# HELP apptainer_sif_count Total number of SIF images in the container store
# TYPE apptainer_sif_count gauge
apptainer_sif_count ${sif_count}

# HELP apptainer_sif_total_bytes Total size of all SIF images in bytes
# TYPE apptainer_sif_total_bytes gauge
apptainer_sif_total_bytes ${sif_size_bytes}

# HELP apptainer_metrics_last_scrape_timestamp Unix timestamp of last metrics collection
# TYPE apptainer_metrics_last_scrape_timestamp gauge
apptainer_metrics_last_scrape_timestamp ${scrape_ts}
EOF

mv "${TMP}" "${OUTPUT}"
