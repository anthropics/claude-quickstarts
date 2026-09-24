"""
Singularity — Snapshot Manager (Fáze 63, v2.0 #3).

Cross-module persistence: register components with a ``dump`` / ``load`` pair,
then snapshot them all into a StateStore (Fáze 62) and restore on boot. This
lets stateful subsystems whose data was previously lost on restart — feature
flags, SLO definitions, webhook subscriptions — survive process restarts and
(with the Redis backend) be shared across instances.

Components stay decoupled: each contributes a pure ``dump() -> jsonable`` and
``load(data)`` callable; the manager just orchestrates and routes through the
StateStore. Dependency-free.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from core.state_store import StateStore


DumpFn = Callable[[], Any]
LoadFn = Callable[[Any], Any]

_NAMESPACE = "snapshot"


@dataclass
class _Component:
    name: str
    dump: DumpFn
    load: LoadFn


class SnapshotManager:
    """Register components and snapshot/restore them via a StateStore."""

    def __init__(self, store: StateStore, *, namespace: str = _NAMESPACE) -> None:
        self.store = store
        self.namespace = namespace
        self._components: dict[str, _Component] = {}
        self._lock = threading.Lock()

        # metrics
        self._snapshots = 0
        self._restores = 0
        self._last_snapshot_at: float | None = None

    # ── Registration ──────────────────────────────────────────────────────────────

    def register(self, name: str, dump: DumpFn, load: LoadFn) -> None:
        if not name:
            raise ValueError("component name is required")
        if not callable(dump) or not callable(load):
            raise ValueError("dump and load must be callable")
        with self._lock:
            self._components[name] = _Component(name, dump, load)

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._components.pop(name, None) is not None

    def list_components(self) -> list[str]:
        with self._lock:
            return sorted(self._components)

    # ── Snapshot / restore ────────────────────────────────────────────────────────

    def snapshot(self, name: str | None = None) -> dict:
        """Persist one component (by name) or all. Returns per-component status."""
        with self._lock:
            comps = ([self._components[name]] if name is not None
                     else list(self._components.values())) if (
                name is None or name in self._components) else None
        if comps is None:
            raise KeyError(f"Unknown component {name!r}")

        result: dict[str, str] = {}
        for c in comps:
            try:
                data = c.dump()
                self.store.set(self.namespace, c.name, data)
                result[c.name] = "ok"
            except Exception as exc:  # component dump must not break the batch
                result[c.name] = f"error: {type(exc).__name__}: {exc}"
        with self._lock:
            self._snapshots += 1
            self._last_snapshot_at = time.time()
        return result

    def restore(self, name: str | None = None) -> dict:
        """Load one component (by name) or all from the store. Missing = skipped."""
        with self._lock:
            comps = ([self._components[name]] if name is not None
                     else list(self._components.values())) if (
                name is None or name in self._components) else None
        if comps is None:
            raise KeyError(f"Unknown component {name!r}")

        result: dict[str, str] = {}
        for c in comps:
            data = self.store.get(self.namespace, c.name)
            if data is None:
                result[c.name] = "no_snapshot"
                continue
            try:
                c.load(data)
                result[c.name] = "restored"
            except Exception as exc:
                result[c.name] = f"error: {type(exc).__name__}: {exc}"
        with self._lock:
            self._restores += 1
        return result

    def has_snapshot(self, name: str) -> bool:
        return self.store.exists(self.namespace, name)

    def clear(self) -> int:
        return self.store.clear(self.namespace)

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            return {
                "components": len(self._components),
                "snapshots": self._snapshots,
                "restores": self._restores,
                "last_snapshot_at": self._last_snapshot_at,
                "namespace": self.namespace,
            }
