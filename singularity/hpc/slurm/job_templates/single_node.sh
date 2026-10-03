#!/usr/bin/env bash
# Single-node DDP training template (1 node × N GPUs).
#
# Usage: sbatch single_node.sh [--train-args ...]

#SBATCH --job-name=agi_single
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=0
#SBATCH --time=1-00:00:00
#SBATCH --partition=gpu_agi
#SBATCH --signal=USR1@90
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=logs/single_%j.out
#SBATCH --error=logs/single_%j.err

set -euo pipefail

SIF_PATH="${SIF_PATH:-/share/groupname/containers/AGI_Core_Env.sif}"
LUSTRE_DATA="${LUSTRE_DATA:-/lustre/groupname/data}"
BURST_BUFFER="${BURST_BUFFER:-/dev/shm/agi_${SLURM_JOB_ID}}"
TRAIN_SCRIPT="${TRAIN_SCRIPT:-$(dirname "${BASH_SOURCE[0]}")/../../training/train_agi.py}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-${BURST_BUFFER}/checkpoints}"

export MASTER_ADDR=localhost
export MASTER_PORT=29500
export WORLD_SIZE="${SLURM_NTASKS_PER_NODE}"
export NODE_RANK=0

export APPTAINER_TMPDIR="${BURST_BUFFER}/apptainer_tmp"
mkdir -p "${APPTAINER_TMPDIR}" "${CHECKPOINT_DIR}"

echo "[$(date -u +%FT%TZ)] Single-node job ${SLURM_JOB_ID} starting (${WORLD_SIZE} GPUs)"

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
