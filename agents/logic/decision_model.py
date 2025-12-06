"""
Decision model for agent choices.

Provides a simple, bounded utility scorer with:
- Value, cost, and risk weighting
- Citation and contradiction penalties
- Hard/soft constraints
- Risk gating and warnings
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class DecisionOption:
    """A single option to score."""
    id: str
    description: str
    value: float = 1.0
    cost: float = 0.0
    risk: float = 0.0  # 0-1
    cited: bool = False
    validated_confidence: float = 0.0
    contradiction_flag: bool = False
    tags: List[str] = field(default_factory=list)
    verified: bool = True  # evidence-backed


@dataclass
class Constraints:
    """Constraints on options."""
    required_tags: List[str] = field(default_factory=list)
    forbidden_tags: List[str] = field(default_factory=list)
    soft_penalties: Dict[str, float] = field(default_factory=dict)  # tag -> penalty
    allow_relaxation: bool = True


@dataclass
class DecisionConfig:
    """Weighting and policy for scoring."""
    value_weight: float = 1.0
    cost_weight: float = 1.0
    risk_weight: float = 1.0
    citation_penalty: float = 0.2  # multiplier penalty if uncited
    contradiction_penalty: float = 0.5  # multiplier penalty if contradictions present
    citation_required: bool = True
    risk_gate: float = 0.8  # above this requires extra evidence/critic


@dataclass
class DecisionResult:
    """Result of scoring options."""
    ranked: List[Dict[str, Any]]
    warnings: List[str]
    blocked: bool
    unverified_penalized: bool = False
    evidence_blocked: bool = False


class DecisionModel:
    """Decision scorer with basic constraints and safety checks."""

    def __init__(self, config: Optional[DecisionConfig] = None):
        self.config = config or DecisionConfig()

    def score_options(
        self,
        options: List[DecisionOption],
        constraints: Optional[Constraints] = None
    ) -> DecisionResult:
        constraints = constraints or Constraints()
        warnings: List[str] = []
        scored = []

        filtered = []
        for opt in options:
            if not self._hard_constraints_ok(opt, constraints):
                warnings.append(f"Option {opt.id} blocked by constraints.")
                continue
            filtered.append(opt)

        if not filtered:
            return DecisionResult(ranked=[], warnings=warnings, blocked=True, evidence_blocked=True)

        unverified_penalized = False
        evidence_blocked = False

        for opt in filtered:
            score, detail_warnings = self._score(opt, constraints)
            if not opt.verified:
                unverified_penalized = True
            if self.config.citation_required and (not opt.cited and not opt.verified):
                evidence_blocked = True
            warnings.extend(detail_warnings)
            scored.append({"id": opt.id, "description": opt.description, "score": score})

        scored.sort(key=lambda x: x["score"], reverse=True)
        if evidence_blocked and all((not o.cited and not o.verified) for o in filtered):
            return DecisionResult(
                ranked=scored,
                warnings=warnings,
                blocked=True,
                unverified_penalized=unverified_penalized,
                evidence_blocked=True
            )
        return DecisionResult(
            ranked=scored,
            warnings=warnings,
            blocked=False,
            unverified_penalized=unverified_penalized,
            evidence_blocked=evidence_blocked
        )

    def _hard_constraints_ok(self, option: DecisionOption, constraints: Constraints) -> bool:
        tags = set(option.tags)
        if constraints.required_tags and not set(constraints.required_tags).issubset(tags):
            return False
        if constraints.forbidden_tags and set(constraints.forbidden_tags) & tags:
            return False
        return True

    def _score(self, option: DecisionOption, constraints: Constraints) -> (float, List[str]):
        c = self.config
        warnings: List[str] = []

        score = (
            c.value_weight * option.value
            - c.cost_weight * option.cost
            - c.risk_weight * option.risk
        )

        if constraints.soft_penalties:
            for tag, penalty in constraints.soft_penalties.items():
                if tag in option.tags:
                    score -= penalty
                    warnings.append(f"Soft penalty applied to {option.id} for tag '{tag}'.")

        if c.citation_required and not option.cited:
            score *= (1 - c.citation_penalty)
            warnings.append(f"Option {option.id} lacks citations; penalized.")

        if option.contradiction_flag:
            score *= (1 - c.contradiction_penalty)
            warnings.append(f"Option {option.id} has contradictions; penalized.")

        if not option.verified:
            score *= (1 - c.citation_penalty)
            warnings.append(f"Option {option.id} is unverified; penalized.")

        if option.risk >= c.risk_gate:
            warnings.append(f"Option {option.id} high risk ({option.risk}); consider extra validation.")

        # Bound score to avoid runaway values
        score = max(-10.0, min(10.0, score))
        return score, warnings
