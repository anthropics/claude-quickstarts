"""
Singularity — Feature Flag Manager (Fáze 56).

Runtime feature gating: toggle capabilities on/off without redeploys, roll a
flag out to a percentage of users, or pin specific users on/off. The platform
already has ~30 static ``enable_*`` settings; this adds dynamic, per-request
control on top.

Rollout is deterministic and sticky: a user falls in the rollout bucket iff
``hash(flag:user) % 100 < percentage``, so the same user gets a stable answer
and buckets grow monotonically as the percentage rises. Dependency-free.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field


@dataclass
class Flag:
    name: str
    enabled: bool = False           # master switch
    rollout: int = 0                # 0–100 percent of users (when enabled)
    on_users: set[str] = field(default_factory=set)   # forced on
    off_users: set[str] = field(default_factory=set)  # forced off
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "rollout": self.rollout,
            "on_users": sorted(self.on_users),
            "off_users": sorted(self.off_users),
            "description": self.description,
        }


def _bucket(flag: str, user: str) -> int:
    """Stable 0–99 bucket for (flag, user)."""
    h = hashlib.sha256(f"{flag}:{user}".encode()).digest()
    return int.from_bytes(h[:4], "big") % 100


# ── Manager ─────────────────────────────────────────────────────────────────────

class FeatureFlagManager:
    """Register flags, then evaluate them per user at runtime."""

    def __init__(self) -> None:
        self._flags: dict[str, Flag] = {}
        self._lock = threading.Lock()

        # metrics
        self._evaluations = 0
        self._enabled_results = 0

    # ── Flag management ───────────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        *,
        enabled: bool = False,
        rollout: int = 0,
        description: str = "",
    ) -> Flag:
        if not name:
            raise ValueError("flag name is required")
        if not 0 <= rollout <= 100:
            raise ValueError("rollout must be in [0, 100]")
        with self._lock:
            flag = Flag(name=name, enabled=enabled, rollout=rollout,
                        description=description)
            self._flags[name] = flag
            return flag

    def set_enabled(self, name: str, enabled: bool) -> bool:
        with self._lock:
            flag = self._flags.get(name)
            if flag is None:
                return False
            flag.enabled = enabled
            return True

    def set_rollout(self, name: str, rollout: int) -> bool:
        if not 0 <= rollout <= 100:
            raise ValueError("rollout must be in [0, 100]")
        with self._lock:
            flag = self._flags.get(name)
            if flag is None:
                return False
            flag.rollout = rollout
            return True

    def set_user_override(self, name: str, user: str, state: bool | None) -> bool:
        """state True = force on, False = force off, None = clear override."""
        with self._lock:
            flag = self._flags.get(name)
            if flag is None:
                return False
            flag.on_users.discard(user)
            flag.off_users.discard(user)
            if state is True:
                flag.on_users.add(user)
            elif state is False:
                flag.off_users.add(user)
            return True

    def delete(self, name: str) -> bool:
        with self._lock:
            return self._flags.pop(name, None) is not None

    def get(self, name: str) -> dict | None:
        with self._lock:
            flag = self._flags.get(name)
            return flag.to_dict() if flag else None

    def list_flags(self) -> list[dict]:
        with self._lock:
            return [f.to_dict() for f in self._flags.values()]

    # ── Snapshot / restore (Fáze 63) ──────────────────────────────────────────────

    def export(self) -> dict:
        """Serialize all flags to a plain dict (for persistence)."""
        with self._lock:
            return {name: f.to_dict() for name, f in self._flags.items()}

    def import_flags(self, data: dict) -> int:
        """Replace flags from an exported dict. Returns the count loaded."""
        with self._lock:
            self._flags.clear()
            for name, d in (data or {}).items():
                self._flags[name] = Flag(
                    name=d["name"],
                    enabled=bool(d.get("enabled", False)),
                    rollout=int(d.get("rollout", 0)),
                    on_users=set(d.get("on_users", [])),
                    off_users=set(d.get("off_users", [])),
                    description=d.get("description", ""),
                )
            return len(self._flags)

    # ── Evaluation ────────────────────────────────────────────────────────────────

    def is_enabled(self, name: str, user: str | None = None) -> bool:
        with self._lock:
            flag = self._flags.get(name)
            self._evaluations += 1
            result = self._evaluate(flag, user)
            if result:
                self._enabled_results += 1
            return result

    @staticmethod
    def _evaluate(flag: Flag | None, user: str | None) -> bool:
        if flag is None:
            return False
        # per-user overrides win, even over the master switch
        if user is not None:
            if user in flag.off_users:
                return False
            if user in flag.on_users:
                return True
        if not flag.enabled:
            return False
        if flag.rollout >= 100:
            return True
        if flag.rollout <= 0:
            return False
        if user is None:
            # no user → treat rollout as all-or-nothing at full only (already
            # handled); partial rollout without a user is not in-bucket
            return False
        return _bucket(flag.name, user) < flag.rollout

    def evaluate_all(self, user: str | None = None) -> dict[str, bool]:
        with self._lock:
            flags = list(self._flags.values())
        out = {}
        for f in flags:
            out[f.name] = self._evaluate(f, user)
        with self._lock:
            self._evaluations += len(flags)
            self._enabled_results += sum(1 for v in out.values() if v)
        return out

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            n = self._evaluations
            return {
                "flags": len(self._flags),
                "evaluations": n,
                "enabled_results": self._enabled_results,
                "enabled_rate": round(self._enabled_results / n, 4) if n else 0.0,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._evaluations = 0
            self._enabled_results = 0
