"""
Singularity — A/B Testing for LLM providers (Fáze 19).

Compares two providers (control vs treatment) with configurable traffic split.
Records per-variant metrics: requests, success rate, avg latency, avg feedback
rating. Fully offline — no external dependencies.
"""
from __future__ import annotations

import random
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

log = structlog.get_logger()


@dataclass
class VariantMetrics:
    requests: int = 0
    successes: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    total_rating: float = 0.0
    rating_count: int = 0

    def record(self, success: bool, latency_ms: float = 0.0, rating: float | None = None) -> None:
        self.requests += 1
        if success:
            self.successes += 1
        else:
            self.failures += 1
        self.total_latency_ms += latency_ms
        if rating is not None:
            self.total_rating += rating
            self.rating_count += 1

    @property
    def success_rate(self) -> float | None:
        return self.successes / self.requests if self.requests else None

    @property
    def avg_latency_ms(self) -> float | None:
        return self.total_latency_ms / self.requests if self.requests else None

    @property
    def avg_rating(self) -> float | None:
        return self.total_rating / self.rating_count if self.rating_count else None

    def to_dict(self) -> dict:
        return {
            "requests": self.requests,
            "successes": self.successes,
            "failures": self.failures,
            "success_rate": round(self.success_rate, 4) if self.success_rate is not None else None,
            "avg_latency_ms": round(self.avg_latency_ms, 2) if self.avg_latency_ms is not None else None,
            "avg_rating": round(self.avg_rating, 2) if self.avg_rating is not None else None,
        }


@dataclass
class ABExperiment:
    experiment_id: str
    name: str
    control_provider: str
    treatment_provider: str
    traffic_split: float              # fraction [0.0–1.0] routed to treatment
    status: str = "active"           # active | paused | completed
    control: VariantMetrics = field(default_factory=VariantMetrics)
    treatment: VariantMetrics = field(default_factory=VariantMetrics)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "control_provider": self.control_provider,
            "treatment_provider": self.treatment_provider,
            "traffic_split": self.traffic_split,
            "status": self.status,
            "created_at": self.created_at,
            "control": self.control.to_dict(),
            "treatment": self.treatment.to_dict(),
        }


_VALID_STATUSES = frozenset({"active", "paused", "completed"})


class ABTestManager:
    """
    Thread-safe manager for A/B experiments.

    Workflow:
        exp_id = mgr.create_experiment("claude-vs-gemini", "claude", "gemini", 0.5)
        provider = mgr.assign_variant(exp_id)   # randomly picks control or treatment
        # ... run task with chosen provider ...
        mgr.record_outcome(exp_id, provider, success=True, latency_ms=320)
    """

    def __init__(self) -> None:
        self._experiments: dict[str, ABExperiment] = {}
        self._lock = threading.Lock()

    def create_experiment(
        self,
        name: str,
        control_provider: str,
        treatment_provider: str,
        traffic_split: float = 0.5,
    ) -> str:
        if not 0.0 <= traffic_split <= 1.0:
            raise ValueError(f"traffic_split must be 0.0–1.0, got {traffic_split}")
        if control_provider == treatment_provider:
            raise ValueError("control_provider and treatment_provider must differ")
        experiment_id = str(uuid.uuid4())
        exp = ABExperiment(
            experiment_id=experiment_id,
            name=name,
            control_provider=control_provider,
            treatment_provider=treatment_provider,
            traffic_split=traffic_split,
        )
        with self._lock:
            self._experiments[experiment_id] = exp
        log.info("ab_experiment_created", experiment_id=experiment_id,
                 control=control_provider, treatment=treatment_provider, split=traffic_split)
        return experiment_id

    def get_experiment(self, experiment_id: str) -> dict | None:
        with self._lock:
            exp = self._experiments.get(experiment_id)
        return exp.to_dict() if exp else None

    def list_experiments(self) -> list[dict]:
        with self._lock:
            items = list(self._experiments.values())
        return [e.to_dict() for e in items]

    def update_experiment(self, experiment_id: str, **kwargs) -> bool:
        """Update status and/or traffic_split. Returns False if not found."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if exp is None:
                return False
            if "status" in kwargs:
                if kwargs["status"] not in _VALID_STATUSES:
                    raise ValueError(f"Invalid status: {kwargs['status']!r}")
                exp.status = kwargs["status"]
            if "traffic_split" in kwargs:
                ts = float(kwargs["traffic_split"])
                if not 0.0 <= ts <= 1.0:
                    raise ValueError(f"traffic_split must be 0.0–1.0, got {ts}")
                exp.traffic_split = ts
        return True

    def delete_experiment(self, experiment_id: str) -> bool:
        with self._lock:
            if experiment_id not in self._experiments:
                return False
            del self._experiments[experiment_id]
        return True

    def assign_variant(self, experiment_id: str) -> str:
        """
        Randomly assign a provider based on traffic_split.
        Raises KeyError if not found; RuntimeError if not active.
        """
        with self._lock:
            exp = self._experiments.get(experiment_id)
        if exp is None:
            raise KeyError(f"No experiment: {experiment_id!r}")
        if exp.status != "active":
            raise RuntimeError(
                f"Experiment {experiment_id!r} is not active (status={exp.status!r})"
            )
        is_treatment = random.random() < exp.traffic_split
        return exp.treatment_provider if is_treatment else exp.control_provider

    def record_outcome(
        self,
        experiment_id: str,
        provider: str,
        success: bool,
        latency_ms: float = 0.0,
        rating: float | None = None,
    ) -> bool:
        """Record a request outcome for the given provider variant. Returns False on mismatch."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if exp is None:
                return False
            if provider == exp.control_provider:
                exp.control.record(success, latency_ms, rating)
            elif provider == exp.treatment_provider:
                exp.treatment.record(success, latency_ms, rating)
            else:
                return False
        log.info("ab_outcome_recorded", experiment_id=experiment_id,
                 provider=provider, success=success, latency_ms=latency_ms)
        return True

    def experiment_count(self) -> int:
        with self._lock:
            return len(self._experiments)
