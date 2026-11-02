"""Proofs about a profile's starting grants, independent of any one session."""

from __future__ import annotations

from typing import Any

from . import policyfile
from .config import Settings
from .policyfile import Bindings
from .prover import Proof, Prover
from .store import Store


def full_policy(store: Store, grants: dict[str, Any], bindings: Bindings) -> dict[str, Any]:
    """Base plus a grants dict (placeholders allowed), rendered for ``bindings``."""
    return policyfile.compose(store.base(bindings), policyfile.render(grants, bindings))


def within_ceiling(settings: Settings, store: Store, prover: Prover, profile: str, grants: dict[str, Any]) -> Proof:
    b = Bindings.sample(settings.api_host, settings.api_port)
    return prover.check(full_policy(store, grants, b), store.ceiling(profile, b))


def no_wider(settings: Settings, store: Store, prover: Prover, new: dict[str, Any], old: dict[str, Any]) -> Proof:
    """Proves ``new`` grants nothing ``old`` did not."""
    b = Bindings.sample(settings.api_host, settings.api_port)
    return prover.check(full_policy(store, new, b), full_policy(store, old, b))
