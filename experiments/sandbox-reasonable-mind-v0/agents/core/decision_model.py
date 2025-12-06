"""
Decision Model System - Phase 2 Enhancement

Implements pluggable utility-based decision scoring with:
- Bounded utility weights and per-role profiles
- Citation requirements and evidence validation
- Hard/soft constraints with relaxation paths
- Risk bands and safe fallbacks
- Integration with plan state and feedback loops
"""

from typing import List, Dict, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import math
import json


class RiskLevel(Enum):
    """Risk levels for decision options."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConstraintType(Enum):
    """Types of constraints on decisions."""
    HARD = "hard"  # Must be satisfied, zeros out option
    SOFT = "soft"  # Penalty if violated
    PREFERENCE = "preference"  # Minor adjustment


class DecisionOutcome(Enum):
    """Outcome of a decision for feedback."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    UNKNOWN = "unknown"


@dataclass
class Citation:
    """A citation backing a claim or score input."""
    source_id: str
    source_type: str  # "fact", "tool_result", "memory", "inference"
    content: str
    confidence: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    trust_weight: float = 1.0  # Source reliability
    
    @property
    def effective_confidence(self) -> float:
        """Confidence adjusted by source trust."""
        return self.confidence * self.trust_weight


@dataclass
class ScoredInput:
    """An input to the utility function with citation."""
    name: str
    value: float
    citations: List[Citation] = field(default_factory=list)
    is_cited: bool = False
    validation_confidence: float = 1.0
    
    @property
    def citation_quality(self) -> float:
        """Average citation quality."""
        if not self.citations:
            return 0.0
        return sum(c.effective_confidence for c in self.citations) / len(self.citations)


@dataclass
class Constraint:
    """A constraint on decision options."""
    name: str
    constraint_type: ConstraintType
    check_fn: Callable[[Dict[str, Any]], bool]
    penalty: float = 0.0  # For soft constraints
    description: str = ""
    relaxable: bool = True  # Can be relaxed in fallback mode
    
    def evaluate(self, option: Dict[str, Any]) -> Tuple[bool, float]:
        """Evaluate constraint, return (satisfied, penalty)."""
        satisfied = self.check_fn(option)
        if satisfied:
            return True, 0.0
        if self.constraint_type == ConstraintType.HARD:
            return False, float('inf')  # Zeros out option
        return False, self.penalty


@dataclass
class DecisionOption:
    """An option being evaluated for selection."""
    option_id: str
    name: str
    description: str
    inputs: Dict[str, ScoredInput] = field(default_factory=dict)
    raw_value: float = 0.0
    cost: float = 0.0
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Computed fields
    utility_score: float = 0.0
    constraint_penalties: Dict[str, float] = field(default_factory=dict)
    is_feasible: bool = True
    blocked_by: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    requires_critic: bool = False
    requires_extra_evidence: bool = False


@dataclass
class DecisionResult:
    """Result of a decision evaluation."""
    selected_option: Optional[DecisionOption]
    all_options: List[DecisionOption]
    selection_reason: str
    confidence: float
    warnings: List[str] = field(default_factory=list)
    required_escalation: bool = False
    fallback_used: bool = False
    critic_invoked: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RoleProfile:
    """Profile defining decision preferences for a role."""
    role_id: str
    name: str
    
    # Utility weights
    value_weight: float = 1.0
    cost_weight: float = 0.3
    risk_weight: float = 0.5
    evidence_weight: float = 0.4
    
    # Thresholds
    citation_threshold: float = 0.6  # Min citation quality
    confidence_threshold: float = 0.5  # Min confidence to proceed
    risk_tolerance: float = 0.5  # 0=conservative, 1=exploratory
    
    # Multipliers
    uncited_penalty: float = 0.3  # Penalty for uncited inputs
    low_confidence_multiplier: float = 0.7  # Applied when confidence < threshold
    contradiction_penalty: float = 0.5  # Penalty for contradicted claims
    
    # Constraints
    max_cost: Optional[float] = None
    max_risk: Optional[float] = None
    required_tools: List[str] = field(default_factory=list)
    forbidden_tools: List[str] = field(default_factory=list)
    
    # Behavior
    require_critic_for_high_risk: bool = True
    allow_abstention: bool = True
    prefer_validated_options: bool = True


# Default role profiles
DEFAULT_PROFILES: Dict[str, RoleProfile] = {
    "researcher": RoleProfile(
        role_id="researcher",
        name="Researcher",
        value_weight=1.2,
        cost_weight=0.2,
        risk_weight=0.4,
        evidence_weight=0.8,
        citation_threshold=0.7,
        confidence_threshold=0.6,
        risk_tolerance=0.4,
        require_critic_for_high_risk=True,
        prefer_validated_options=True
    ),
    "operator": RoleProfile(
        role_id="operator",
        name="Operator",
        value_weight=0.8,
        cost_weight=0.6,
        risk_weight=0.6,
        evidence_weight=0.3,
        citation_threshold=0.4,
        confidence_threshold=0.4,
        risk_tolerance=0.6,
        require_critic_for_high_risk=False,
        prefer_validated_options=False
    ),
    "conservative": RoleProfile(
        role_id="conservative",
        name="Conservative",
        value_weight=0.7,
        cost_weight=0.4,
        risk_weight=0.9,
        evidence_weight=0.6,
        citation_threshold=0.8,
        confidence_threshold=0.7,
        risk_tolerance=0.2,
        require_critic_for_high_risk=True,
        prefer_validated_options=True
    ),
    "exploratory": RoleProfile(
        role_id="exploratory",
        name="Exploratory",
        value_weight=1.5,
        cost_weight=0.3,
        risk_weight=0.3,
        evidence_weight=0.3,
        citation_threshold=0.3,
        confidence_threshold=0.3,
        risk_tolerance=0.8,
        require_critic_for_high_risk=False,
        prefer_validated_options=False
    ),
    "balanced": RoleProfile(
        role_id="balanced",
        name="Balanced",
        value_weight=1.0,
        cost_weight=0.4,
        risk_weight=0.5,
        evidence_weight=0.5,
        citation_threshold=0.5,
        confidence_threshold=0.5,
        risk_tolerance=0.5,
        require_critic_for_high_risk=True,
        prefer_validated_options=True
    )
}


class UtilityFunction(ABC):
    """Abstract base class for utility functions."""
    
    @abstractmethod
    def compute(
        self,
        option: DecisionOption,
        profile: RoleProfile,
        context: Dict[str, Any]
    ) -> float:
        """Compute utility score for an option."""
        ...


class StandardUtilityFunction(UtilityFunction):
    """
    Standard utility function: U = value - cost_penalty - risk_penalty
    
    With adjustments for:
    - Citation quality
    - Validation confidence
    - Contradiction penalties
    """
    
    def __init__(self, weight_bounds: Tuple[float, float] = (0.0, 2.0)):
        self.weight_bounds = weight_bounds
    
    def _bound_weight(self, weight: float) -> float:
        """Keep weights within bounds."""
        return max(self.weight_bounds[0], min(self.weight_bounds[1], weight))
    
    def compute(
        self,
        option: DecisionOption,
        profile: RoleProfile,
        context: Dict[str, Any]
    ) -> float:
        """Compute bounded utility score."""
        # Base utility components
        value_component = option.raw_value * self._bound_weight(profile.value_weight)
        cost_component = option.cost * self._bound_weight(profile.cost_weight)
        risk_component = option.risk_score * self._bound_weight(profile.risk_weight)
        
        # Base utility
        utility = value_component - cost_component - risk_component
        
        # Evidence quality adjustment
        evidence_factor = self._compute_evidence_factor(option, profile)
        utility *= evidence_factor
        
        # Apply constraint penalties
        for penalty_name, penalty_value in option.constraint_penalties.items():
            if penalty_value == float('inf'):
                return float('-inf')  # Hard constraint violated
            utility -= penalty_value
        
        # Tie-breaker: prefer validated options
        if profile.prefer_validated_options:
            citation_bonus = self._citation_bonus(option, profile)
            utility += citation_bonus * 0.1  # Small bonus
        
        return utility
    
    def _compute_evidence_factor(
        self,
        option: DecisionOption,
        profile: RoleProfile
    ) -> float:
        """Compute evidence quality factor (0-1)."""
        if not option.inputs:
            return profile.low_confidence_multiplier
        
        # Average citation quality across inputs
        cited_inputs = [inp for inp in option.inputs.values() if inp.is_cited]
        if not cited_inputs:
            return 1.0 - (profile.uncited_penalty * profile.evidence_weight)
        
        avg_quality = sum(inp.citation_quality for inp in cited_inputs) / len(cited_inputs)
        
        if avg_quality < profile.citation_threshold:
            return profile.low_confidence_multiplier
        
        return min(1.0, avg_quality)
    
    def _citation_bonus(self, option: DecisionOption, profile: RoleProfile) -> float:
        """Compute citation bonus for tie-breaking."""
        if not option.inputs:
            return 0.0
        
        cited_count = sum(1 for inp in option.inputs.values() if inp.is_cited)
        return cited_count / len(option.inputs) * profile.evidence_weight


class DecisionModel:
    """
    Pluggable decision model with utility scoring.
    
    Features:
    - Per-role profiles with different weightings
    - Citation requirements and validation
    - Hard/soft constraints with relaxation
    - Risk bands and escalation
    - Integration with plan state
    - Feedback loop for weight adaptation
    """
    
    def __init__(
        self,
        profile: Optional[RoleProfile] = None,
        utility_fn: Optional[UtilityFunction] = None
    ):
        self.profile = profile or DEFAULT_PROFILES["balanced"]
        self.utility_fn = utility_fn or StandardUtilityFunction()
        self.constraints: List[Constraint] = []
        self.decision_history: List[Dict[str, Any]] = []
        self.weight_adjustments: Dict[str, float] = {}
        
        # Safe fallback option
        self.fallback_option: Optional[DecisionOption] = None
    
    def set_profile(self, profile_id: str) -> None:
        """Load a role profile."""
        if profile_id in DEFAULT_PROFILES:
            self.profile = DEFAULT_PROFILES[profile_id]
        else:
            raise ValueError(f"Unknown profile: {profile_id}")
    
    def set_custom_profile(self, profile: RoleProfile) -> None:
        """Set a custom role profile."""
        self.profile = profile
    
    def add_constraint(self, constraint: Constraint) -> None:
        """Add a constraint to the decision model."""
        self.constraints.append(constraint)
    
    def clear_constraints(self) -> None:
        """Clear all constraints."""
        self.constraints.clear()
    
    def set_fallback(self, option: DecisionOption) -> None:
        """Set a safe fallback option."""
        self.fallback_option = option
    
    def compute_risk_level(self, option: DecisionOption) -> RiskLevel:
        """Compute risk level from risk score."""
        score = option.risk_score
        if score < 0.25:
            return RiskLevel.LOW
        elif score < 0.5:
            return RiskLevel.MEDIUM
        elif score < 0.75:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    def evaluate_options(
        self,
        options: List[DecisionOption],
        context: Optional[Dict[str, Any]] = None,
        allow_relaxation: bool = True
    ) -> DecisionResult:
        """
        Evaluate options and select the best one.
        
        Args:
            options: List of options to evaluate
            context: Current plan state, tool results, etc.
            allow_relaxation: Whether to relax constraints if all blocked
        
        Returns:
            DecisionResult with selected option and metadata
        """
        context = context or {}
        warnings: List[str] = []
        critic_invoked = False
        fallback_used = False
        
        if not options:
            if self.fallback_option:
                return DecisionResult(
                    selected_option=self.fallback_option,
                    all_options=[],
                    selection_reason="No options provided, using fallback",
                    confidence=0.3,
                    warnings=["No options provided"],
                    fallback_used=True
                )
            return DecisionResult(
                selected_option=None,
                all_options=[],
                selection_reason="No options available",
                confidence=0.0,
                warnings=["No options to evaluate"],
                required_escalation=True
            )
        
        # Step 1: Validate citations and compute evidence quality
        for option in options:
            self._validate_citations(option)
            option.risk_level = self.compute_risk_level(option)
        
        # Step 2: Apply constraints
        feasible_options = []
        for option in options:
            self._apply_constraints(option)
            if option.is_feasible:
                feasible_options.append(option)
        
        # Step 3: Handle no feasible options
        if not feasible_options:
            if allow_relaxation:
                # Try relaxing soft constraints
                relaxed = self._relax_constraints(options)
                if relaxed:
                    feasible_options = relaxed
                    warnings.append("Soft constraints relaxed to find feasible options")
                    fallback_used = True
            
            if not feasible_options:
                # Use fallback if available
                if self.fallback_option:
                    return DecisionResult(
                        selected_option=self.fallback_option,
                        all_options=options,
                        selection_reason="All options blocked by constraints, using fallback",
                        confidence=0.2,
                        warnings=["All options blocked"] + [
                            f"{o.name}: blocked by {o.blocked_by}" for o in options
                        ],
                        fallback_used=True,
                        required_escalation=True
                    )
                
                # Escalate
                return DecisionResult(
                    selected_option=None,
                    all_options=options,
                    selection_reason="All options blocked by constraints",
                    confidence=0.0,
                    warnings=["All options blocked, escalation required"],
                    required_escalation=True
                )
        
        # Step 4: Compute utility scores
        for option in feasible_options:
            option.utility_score = self.utility_fn.compute(option, self.profile, context)
            
            # Check if high-risk requires critic
            if option.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                if self.profile.require_critic_for_high_risk:
                    option.requires_critic = True
                option.requires_extra_evidence = True
                warnings.append(f"Option '{option.name}' is high-risk")
        
        # Step 5: Sort by utility
        feasible_options.sort(key=lambda x: x.utility_score, reverse=True)
        
        # Step 6: Select best option with sanity checks
        selected = feasible_options[0]
        
        # Sanity check: don't select if utility is extremely negative
        if selected.utility_score < -10:
            if self.fallback_option:
                return DecisionResult(
                    selected_option=self.fallback_option,
                    all_options=options,
                    selection_reason="Best option has unacceptable utility, using fallback",
                    confidence=0.3,
                    warnings=["Best option utility too low"],
                    fallback_used=True
                )
        
        # Check if critic is required
        if selected.requires_critic:
            critic_invoked = True
            warnings.append("Critic pass required for selected option")
        
        # Compute confidence based on utility gap and evidence quality
        confidence = self._compute_selection_confidence(selected, feasible_options)
        
        # Log decision for feedback loop
        self._log_decision(selected, feasible_options, context)
        
        return DecisionResult(
            selected_option=selected,
            all_options=options,
            selection_reason=f"Highest utility: {selected.utility_score:.3f}",
            confidence=confidence,
            warnings=warnings + selected.warnings,
            fallback_used=fallback_used,
            critic_invoked=critic_invoked
        )
    
    def _validate_citations(self, option: DecisionOption) -> None:
        """Validate citations for option inputs."""
        for input_name, scored_input in option.inputs.items():
            if not scored_input.citations:
                scored_input.is_cited = False
                option.warnings.append(f"Input '{input_name}' has no citations")
            else:
                scored_input.is_cited = True
                # Check citation quality
                avg_quality = scored_input.citation_quality
                if avg_quality < self.profile.citation_threshold:
                    option.warnings.append(
                        f"Input '{input_name}' citation quality ({avg_quality:.2f}) "
                        f"below threshold ({self.profile.citation_threshold:.2f})"
                    )
    
    def _apply_constraints(self, option: DecisionOption) -> None:
        """Apply all constraints to an option."""
        option.is_feasible = True
        option.constraint_penalties.clear()
        option.blocked_by.clear()
        
        option_dict = {
            "option_id": option.option_id,
            "name": option.name,
            "cost": option.cost,
            "risk_score": option.risk_score,
            "risk_level": option.risk_level,
            "raw_value": option.raw_value,
            **option.metadata
        }
        
        for constraint in self.constraints:
            satisfied, penalty = constraint.evaluate(option_dict)
            if not satisfied:
                if constraint.constraint_type == ConstraintType.HARD:
                    option.is_feasible = False
                    option.blocked_by.append(constraint.name)
                else:
                    option.constraint_penalties[constraint.name] = penalty
    
    def _relax_constraints(
        self,
        options: List[DecisionOption]
    ) -> List[DecisionOption]:
        """Try relaxing soft constraints to find feasible options."""
        # Get only hard constraints
        hard_constraints = [
            c for c in self.constraints
            if c.constraint_type == ConstraintType.HARD and not c.relaxable
        ]
        
        relaxed_options = []
        for option in options:
            option.is_feasible = True
            option.constraint_penalties.clear()
            option.blocked_by.clear()
            
            option_dict = {
                "option_id": option.option_id,
                "name": option.name,
                "cost": option.cost,
                "risk_score": option.risk_score,
                "risk_level": option.risk_level,
                "raw_value": option.raw_value,
                **option.metadata
            }
            
            blocked = False
            for constraint in hard_constraints:
                satisfied, _ = constraint.evaluate(option_dict)
                if not satisfied:
                    blocked = True
                    option.blocked_by.append(constraint.name)
                    break
            
            if not blocked:
                option.warnings.append("Constraints relaxed for this option")
                relaxed_options.append(option)
        
        return relaxed_options
    
    def _compute_selection_confidence(
        self,
        selected: DecisionOption,
        all_options: List[DecisionOption]
    ) -> float:
        """Compute confidence in the selection."""
        if len(all_options) == 1:
            # Only one option, confidence based on its quality
            base_conf = 0.5
        else:
            # Confidence based on utility gap to second-best
            second_best = all_options[1] if len(all_options) > 1 else None
            if second_best:
                gap = selected.utility_score - second_best.utility_score
                base_conf = min(0.9, 0.5 + gap * 0.2)
            else:
                base_conf = 0.6
        
        # Adjust for evidence quality
        if selected.inputs:
            cited_ratio = sum(1 for i in selected.inputs.values() if i.is_cited) / len(selected.inputs)
            base_conf *= (0.5 + 0.5 * cited_ratio)
        
        # Adjust for risk
        if selected.risk_level == RiskLevel.HIGH:
            base_conf *= 0.8
        elif selected.risk_level == RiskLevel.CRITICAL:
            base_conf *= 0.6
        
        return min(1.0, max(0.0, base_conf))
    
    def _log_decision(
        self,
        selected: DecisionOption,
        all_options: List[DecisionOption],
        context: Dict[str, Any]
    ) -> None:
        """Log decision for feedback loop."""
        self.decision_history.append({
            "timestamp": datetime.now().isoformat(),
            "selected": selected.option_id,
            "selected_utility": selected.utility_score,
            "options_count": len(all_options),
            "profile": self.profile.role_id,
            "context_keys": list(context.keys()),
            "outcome": None  # To be updated later
        })
    
    def record_outcome(
        self,
        decision_index: int,
        outcome: DecisionOutcome,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record outcome of a past decision for feedback."""
        if 0 <= decision_index < len(self.decision_history):
            self.decision_history[decision_index]["outcome"] = outcome.value
            self.decision_history[decision_index]["outcome_details"] = details
    
    def adapt_weights(
        self,
        learning_rate: float = 0.1,
        min_samples: int = 5
    ) -> Dict[str, float]:
        """
        Adapt weights based on decision outcomes.
        
        Uses bounded updates to prevent oscillation.
        """
        # Filter decisions with outcomes
        completed = [
            d for d in self.decision_history
            if d.get("outcome") is not None
        ]
        
        if len(completed) < min_samples:
            return {}
        
        # Compute success rate
        successes = sum(1 for d in completed if d["outcome"] == "success")
        success_rate = successes / len(completed)
        
        adjustments = {}
        
        # If success rate is low, increase evidence weight
        if success_rate < 0.5:
            delta = learning_rate * (0.5 - success_rate)
            adjustments["evidence_weight"] = min(0.1, delta)
            adjustments["risk_weight"] = min(0.1, delta)
        
        # If success rate is high, can slightly reduce conservatism
        if success_rate > 0.8:
            delta = learning_rate * (success_rate - 0.8)
            adjustments["value_weight"] = min(0.05, delta)
        
        # Apply bounded adjustments
        for key, delta in adjustments.items():
            current = getattr(self.profile, key, 0.5)
            new_value = max(0.1, min(2.0, current + delta))
            setattr(self.profile, key, new_value)
            self.weight_adjustments[key] = delta
        
        return adjustments
    
    def get_decision_stats(self) -> Dict[str, Any]:
        """Get statistics on decision history."""
        if not self.decision_history:
            return {"total_decisions": 0}
        
        completed = [d for d in self.decision_history if d.get("outcome")]
        outcomes = {}
        for d in completed:
            outcome = d["outcome"]
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        
        return {
            "total_decisions": len(self.decision_history),
            "completed_decisions": len(completed),
            "outcomes": outcomes,
            "weight_adjustments": self.weight_adjustments,
            "current_profile": self.profile.role_id
        }


class ContradictionDetector:
    """
    Detects contradictions in evidence and claims.
    
    Policy options: block or penalize contradicted options.
    """
    
    def __init__(self, policy: str = "penalize"):
        self.policy = policy  # "block" or "penalize"
        self.penalty_amount = 0.3
    
    def detect_contradictions(
        self,
        citations: List[Citation]
    ) -> List[Tuple[Citation, Citation, str]]:
        """Detect contradictions between citations."""
        contradictions = []
        
        for i, c1 in enumerate(citations):
            for c2 in citations[i+1:]:
                if self._are_contradictory(c1.content, c2.content):
                    reason = f"'{c1.content[:50]}' contradicts '{c2.content[:50]}'"
                    contradictions.append((c1, c2, reason))
        
        return contradictions
    
    def _are_contradictory(self, s1: str, s2: str) -> bool:
        """Simple contradiction detection."""
        s1_lower = s1.lower()
        s2_lower = s2.lower()
        
        # Check for negation patterns
        negation_patterns = [" not ", " no ", " never ", " cannot ", " won't "]
        
        for pattern in negation_patterns:
            if pattern in s1_lower:
                base = s1_lower.replace(pattern, " ")
                if base.strip() == s2_lower.strip():
                    return True
            if pattern in s2_lower:
                base = s2_lower.replace(pattern, " ")
                if base.strip() == s1_lower.strip():
                    return True
        
        return False
    
    def apply_to_option(
        self,
        option: DecisionOption
    ) -> Tuple[bool, List[str]]:
        """
        Check option for contradictions and apply policy.
        
        Returns:
            (is_blocked, list of contradiction messages)
        """
        all_citations = []
        for scored_input in option.inputs.values():
            all_citations.extend(scored_input.citations)
        
        contradictions = self.detect_contradictions(all_citations)
        
        if not contradictions:
            return False, []
        
        messages = [reason for _, _, reason in contradictions]
        
        if self.policy == "block":
            option.is_feasible = False
            option.blocked_by.append("contradictions")
            return True, messages
        else:
            # Penalize
            penalty = self.penalty_amount * len(contradictions)
            option.constraint_penalties["contradictions"] = penalty
            option.warnings.extend([f"Contradiction: {m}" for m in messages])
            return False, messages


class RiskGate:
    """
    Gate that requires extra validation for high-risk options.
    """
    
    def __init__(
        self,
        require_critic: bool = True,
        require_extra_evidence: bool = True,
        max_risk_without_gate: RiskLevel = RiskLevel.MEDIUM
    ):
        self.require_critic = require_critic
        self.require_extra_evidence = require_extra_evidence
        self.max_risk_without_gate = max_risk_without_gate
    
    def check(self, option: DecisionOption) -> Dict[str, Any]:
        """Check if option requires gating."""
        needs_gate = False
        requirements = []
        
        risk_order = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3
        }
        
        if risk_order[option.risk_level] > risk_order[self.max_risk_without_gate]:
            needs_gate = True
            if self.require_critic:
                requirements.append("critic_pass")
                option.requires_critic = True
            if self.require_extra_evidence:
                requirements.append("extra_evidence")
                option.requires_extra_evidence = True
        
        return {
            "needs_gate": needs_gate,
            "requirements": requirements,
            "risk_level": option.risk_level.value
        }


def create_decision_model(
    profile_id: str = "balanced",
    custom_constraints: Optional[List[Constraint]] = None
) -> DecisionModel:
    """Factory function to create a configured decision model."""
    model = DecisionModel()
    model.set_profile(profile_id)
    
    if custom_constraints:
        for constraint in custom_constraints:
            model.add_constraint(constraint)
    
    return model
