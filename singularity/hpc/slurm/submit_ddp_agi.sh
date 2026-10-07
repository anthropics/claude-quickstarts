#!/usr/bin/env bash
# Slurm submission script for multi-node DDP AGI training via Apptainer.
#
# Submit: sbatch submit_ddp_agi.sh [--train-args ...]
# Requires: SIF_PATH and LUSTRE_DATA env vars set, or override below.

#SBATCH --job-name=agi_ddp
#SBATCH --nodes=8
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=0                          # request all memory on node
#SBATCH --time=2-00:00:00
#SBATCH --partition=gpu_agi
#SBATCH --signal=USR1@90                 # SIGUSR1 90s before time limit
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=logs/agi_%j_%N.out
#SBATCH --error=logs/agi_%j_%N.err

set -euo pipefail

# ── Paths (override via env or sbatch --export) ────────────────────────────
SIF_PATH="${SIF_PATH:-/share/groupname/containers/AGI_Core_Env.sif}"
LUSTRE_DATA="${LUSTRE_DATA:-/lustre/groupname/data}"
BURST_BUFFER="${BURST_BUFFER:-/dev/shm/agi_${SLURM_JOB_ID}}"
TRAIN_SCRIPT="${TRAIN_SCRIPT:-$(dirname "${BASH_SOURCE[0]}")/../training/train_agi.py}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-${BURST_BUFFER}/checkpoints}"

# ── Environment ────────────────────────────────────────────────────────────
export MASTER_ADDR=$(scontrol show hostnames "${SLURM_JOB_NODELIST}" | head -1)
export MASTER_PORT=29500
export WORLD_SIZE=$((SLURM_NNODES * SLURM_NTASKS_PER_NODE))
export NODE_RANK="${SLURM_NODEID}"
export LOCAL_RANK="${SLURM_LOCALID}"

# Apptainer scratch on NVMe burst buffer (avoid Lustre contention)
export APPTAINER_TMPDIR="${BURST_BUFFER}/apptainer_tmp"
mkdir -p "${APPTAINER_TMPDIR}" "${CHECKPOINT_DIR}"

echo "[$(date -u +%FT%TZ)] Job ${SLURM_JOB_ID} starting on ${SLURM_NNODES} nodes"
echo "  MASTER_ADDR=${MASTER_ADDR}  WORLD_SIZE=${WORLD_SIZE}"
echo "  SIF=${SIF_PATH}  DATA=${LUSTRE_DATA}"

# ── Verify SIF before launch (exit early on tampered image) ───────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/../apptainer/verify.sh" ]]; then
    bash "${SCRIPT_DIR}/../apptainer/verify.sh" "${SIF_PATH}" || {
        echo "ERROR: SIF verification failed — aborting." >&2
        exit 1
    }
fi

# ── Launch DDP workload ────────────────────────────────────────────────────
srun --kill-on-bad-exit=1 \
    apptainer exec \
        --nv \
        --bind "${LUSTRE_DATA}:/mnt/datafiles" \
        --bind "${CHECKPOINT_DIR}:/mnt/checkpoints" \
        --bind "${APPTAINER_TMPDIR}:/tmp" \
        "${SIF_PATH}" \
    python "${TRAIN_SCRIPT}" \
        --data-dir /mnt/datafiles \
        --checkpoint-dir /mnt/checkpoints \
        "${@}"

echo "[$(date -u +%FT%TZ)] Job ${SLURM_JOB_ID} finished."
