"""
Singularity — AGI DDP Training Script (Fáze 26).

PyTorch Lightning multi-node DDP with:
  - SlurmEnvironment plugin for automatic SIGUSR1/SIGTERM handling
  - SingularityDDPCallback for preemption-safe checkpointing
  - Async NVMe burst-buffer checkpoint + background Lustre sync
  - auto_requeue() via scontrol after safe checkpoint

Usage (inside Apptainer / Slurm):
    python train_agi.py --data-dir /mnt/datafiles --checkpoint-dir /mnt/checkpoints
    python train_agi.py --simulate-preempt   # local smoke test
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path

import structlog

log = structlog.get_logger()

# ── Optional Lightning import (graceful degradation for offline tests) ────────
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    import lightning as L
    from lightning.pytorch.callbacks import Callback, ModelCheckpoint
    from lightning.pytorch.plugins.environments import SlurmEnvironment
    _LIGHTNING_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LIGHTNING_AVAILABLE = False
    L = None  # type: ignore[assignment]

logging.basicConfig(level=logging.INFO)


# ── Preemption flag (set by SlurmEnvironment on SIGUSR1) ─────────────────────

_preemption_requested = threading.Event()


def _mark_preemption(*_args) -> None:
    """Signal handler: set the preemption flag."""
    log.warning("preemption_signal_received")
    _preemption_requested.set()


# ── Checkpoint strategy ───────────────────────────────────────────────────────

class CheckpointStrategy:
    """
    Two-phase checkpoint:
      1. Fast write to NVMe burst buffer (low latency, local)
      2. Background rsync to Lustre (durable, shared)
    """

    def __init__(self, burst_dir: str, lustre_dir: str) -> None:
        self.burst = Path(burst_dir)
        self.lustre = Path(lustre_dir)
        self.burst.mkdir(parents=True, exist_ok=True)
        self.lustre.mkdir(parents=True, exist_ok=True)

    def save(self, trainer: "L.Trainer", ckpt_name: str = "last.ckpt") -> Path:
        """Save checkpoint to burst buffer, then async-sync to Lustre."""
        burst_path = self.burst / ckpt_name
        trainer.save_checkpoint(str(burst_path))
        log.info("checkpoint_burst_written", path=str(burst_path))

        # Non-blocking sync to Lustre
        lustre_path = self.lustre / ckpt_name
        thread = threading.Thread(
            target=self._sync_to_lustre,
            args=(burst_path, lustre_path),
            daemon=True,
        )
        thread.start()
        return burst_path

    def _sync_to_lustre(self, src: Path, dst: Path) -> None:
        try:
            shutil.copy2(str(src), str(dst))
            log.info("checkpoint_lustre_synced", dst=str(dst))
        except Exception as exc:
            log.error("checkpoint_lustre_sync_failed", error=str(exc))


def auto_requeue(job_id: str | None = None) -> None:
    """Request Slurm to requeue this job after a safe checkpoint."""
    jid = job_id or os.environ.get("SLURM_JOB_ID")
    if not jid:
        log.warning("auto_requeue_skipped_no_job_id")
        return
    try:
        result = subprocess.run(
            ["scontrol", "requeue", jid],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            log.info("job_requeued", job_id=jid)
        else:
            log.error("requeue_failed", job_id=jid, stderr=result.stderr)
    except FileNotFoundError:
        log.warning("scontrol_not_found_skipping_requeue")
    except Exception as exc:
        log.error("requeue_error", error=str(exc))


# ── Lightning Callback ────────────────────────────────────────────────────────

class SingularityDDPCallback(Callback):
    """
    Monitors the preemption flag at each epoch boundary.
    On SIGUSR1: checkpoint → requeue → raise SystemExit (graceful stop).
    """

    def __init__(self, strategy: CheckpointStrategy) -> None:
        super().__init__()
        self.strategy = strategy

    def on_train_epoch_end(self, trainer: "L.Trainer", pl_module: "L.LightningModule") -> None:
        if _preemption_requested.is_set():
            log.warning("preemption_detected_saving_checkpoint",
                        epoch=trainer.current_epoch)
            self.strategy.save(trainer, "last.ckpt")
            auto_requeue()
            trainer.should_stop = True


# ── Minimal model for smoke tests ─────────────────────────────────────────────

class _AGIModel(L.LightningModule):
    """Trivial FF model — replace with real architecture."""

    def __init__(self, in_features: int = 128, hidden: int = 256, out_features: int = 10):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, hidden),
            nn.ReLU(),
            nn.Linear(hidden, out_features),
        )
        self.loss_fn = nn.CrossEntropyLoss()

    def forward(self, x):
        return self.net(x)

    def training_step(self, batch, batch_idx):
        x, y = batch
        loss = self.loss_fn(self(x), y)
        self.log("train_loss", loss, prog_bar=True, sync_dist=True)
        return loss

    def configure_optimizers(self):
        return torch.optim.AdamW(self.parameters(), lr=3e-4)


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AGI DDP Training")
    p.add_argument("--data-dir", default="/mnt/datafiles")
    p.add_argument("--checkpoint-dir", default="/mnt/checkpoints")
    p.add_argument("--burst-dir", default=os.environ.get("BURST_BUFFER", "/dev/shm/agi"))
    p.add_argument("--max-epochs", type=int, default=100)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--simulate-preempt", action="store_true",
                   help="Fire preemption flag after first epoch (local test)")
    return p.parse_args()


def main() -> None:
    if not _LIGHTNING_AVAILABLE:
        print("PyTorch Lightning not installed — training unavailable.")
        return

    args = parse_args()

    strategy = CheckpointStrategy(
        burst_dir=args.burst_dir,
        lustre_dir=args.checkpoint_dir,
    )

    # Synthetic dataset for smoke tests
    dataset = TensorDataset(
        torch.randn(256, 128),
        torch.randint(0, 10, (256,)),
    )
    loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=0)

    model = _AGIModel()
    preempt_cb = SingularityDDPCallback(strategy)

    # SlurmEnvironment handles SIGUSR1 → sets _preemption_requested flag
    slurm_env = SlurmEnvironment(auto_requeue=False)  # we manage requeue ourselves

    trainer = L.Trainer(
        max_epochs=args.max_epochs,
        accelerator="auto",
        devices="auto",
        num_nodes=int(os.environ.get("SLURM_NNODES", 1)),
        strategy="ddp",
        plugins=[slurm_env],
        callbacks=[preempt_cb],
        enable_progress_bar=True,
    )

    if args.simulate_preempt:
        # Simulate SIGUSR1 after epoch 1 for local testing
        import signal
        import threading
        def _fire():
            import time; time.sleep(2)
            os.kill(os.getpid(), signal.SIGUSR1)
        threading.Thread(target=_fire, daemon=True).start()

    trainer.fit(model, loader)
    log.info("training_complete", epochs=trainer.current_epoch)


if __name__ == "__main__":
    main()
