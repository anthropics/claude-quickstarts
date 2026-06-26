#!/usr/bin/env bash
# Multi-node DDP training template (N nodes × G GPUs each).
# Parameterize via environment variables before submitting.
#
# Example: NNODES=16 sbatch multi_node.sh --config large_model.yaml

#SBATCH --job-name=agi_multi
#SBATCH --nodes=${NNODES:-8}
#SBATCH --ntasks-per-node=${GPUS_PER_NODE:-8}
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=0
#SBATCH --time=7-00:00:00
#SBATCH --partition=gpu_agi
#SBATCH --signal=USR1@90
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=logs/multi_%j_%N.out
#SBATCH --error=logs/multi_%j_%N.err
#SBATCH --mail-type=FAIL,TIME_LIMIT_90
#SBATCH --mail-user=${NOTIFY_EMAIL:-root@localhost}

set -euo pipefail

SIF_PATH="${SIF_PATH:-/share/groupname/containers/AGI_Core_Env.sif}"
LUSTRE_DATA="${LUSTRE_DATA:-/lustre/groupname/data}"
BURST_BUFFER="${BURST_BUFFER:-/dev/shm/agi_${SLURM_JOB_ID}}"
TRAIN_SCRIPT="${TRAIN_SCRIPT:-$(dirname "${BASH_SOURCE[0]}")/../../training/train_agi.py}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-${BURST_BUFFER}/checkpoints}"

export MASTER_ADDR=$(scontrol show hostnames "${SLURM_JOB_NODELIST}" | head -1)
export MASTER_PORT=29500
export WORLD_SIZE=$((SLURM_NNODES * SLURM_NTASKS_PER_NODE))
export NODE_RANK="${SLURM_NODEID}"

export APPTAINER_TMPDIR="${BURST_BUFFER}/apptainer_tmp"
mkdir -p "${APPTAINER_TMPDIR}" "${CHECKPOINT_DIR}"

echo "[$(date -u +%FT%TZ)] Multi-node job ${SLURM_JOB_ID}: ${SLURM_NNODES} nodes × ${SLURM_NTASKS_PER_NODE} GPUs = ${WORLD_SIZE} ranks"
echo "  MASTER=${MASTER_ADDR}:${MASTER_PORT}"

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
