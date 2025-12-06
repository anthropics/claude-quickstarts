"""
Fuzzy and Probabilistic Inference - Advanced Enhancement

Provides fuzzy logic and probabilistic reasoning:
- Fuzzy membership functions
- Confidence intervals
- Log-odds/Bayesian updates
- Soft constraint satisfaction
- Probabilistic inference chains
"""

from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import math


class FuzzyMembershipType(Enum):
    """Types of fuzzy membership functions."""
    TRIANGULAR = "triangular"
    TRAPEZOIDAL = "trapezoidal"
    GAUSSIAN = "gaussian"
    SIGMOID = "sigmoid"
    PIECEWISE = "piecewise"


class InferenceMode(Enum):
    """Modes of probabilistic inference."""
    BINARY = "binary"  # Traditional true/false
    FUZZY = "fuzzy"  # Fuzzy membership [0,1]
    BAYESIAN = "bayesian"  # Log-odds updates
    INTERVAL = "interval"  # Confidence intervals


@dataclass
class ConfidenceInterval:
    """A confidence interval with lower and upper bounds."""
    lower: float
    point: float  # Point estimate
    upper: float
    confidence_level: float = 0.95  # e.g., 95% CI
    
    def __post_init__(self):
        self.lower = max(0.0, min(1.0, self.lower))
        self.upper = max(0.0, min(1.0, self.upper))
        self.point = max(self.lower, min(self.upper, self.point))
    
    @property
    def width(self) -> float:
        """Width of the interval (uncertainty)."""
        return self.upper - self.lower
    
    @property
    def uncertainty(self) -> float:
        """Normalized uncertainty score."""
        return self.width
    
    def contains(self, value: float) -> bool:
        """Check if value is within interval."""
        return self.lower <= value <= self.upper
    
    def overlaps(self, other: "ConfidenceInterval") -> bool:
        """Check if intervals overlap."""
        return self.lower <= other.upper and other.lower <= self.upper
    
    def combine_with(self, other: "ConfidenceInterval") -> "ConfidenceInterval":
        """Combine two intervals (intersection if overlapping, else union)."""
        if self.overlaps(other):
            # Intersection - narrow the bounds
            return ConfidenceInterval(
                lower=max(self.lower, other.lower),
                point=(self.point + other.point) / 2,
                upper=min(self.upper, other.upper),
                confidence_level=min(self.confidence_level, other.confidence_level)
            )
        else:
            # Wider uncertainty when disjoint
            return ConfidenceInterval(
                lower=min(self.lower, other.lower),
                point=(self.point + other.point) / 2,
                upper=max(self.upper, other.upper),
                confidence_level=min(self.confidence_level, other.confidence_level) * 0.8
            )


@dataclass
class LogOdds:
    """Log-odds representation for Bayesian updates."""
    log_odds: float  # log(p / (1-p))
    
    @classmethod
    def from_probability(cls, p: float) -> "LogOdds":
        """Convert probability to log-odds."""
        p = max(1e-10, min(1 - 1e-10, p))
        return cls(log_odds=math.log(p / (1 - p)))
    
    def to_probability(self) -> float:
        """Convert back to probability."""
        return 1 / (1 + math.exp(-self.log_odds))
    
    def update(self, evidence_log_odds: float) -> "LogOdds":
        """Bayesian update with evidence log-odds."""
        return LogOdds(log_odds=self.log_odds + evidence_log_odds)
    
    def update_with_likelihood_ratio(self, lr: float) -> "LogOdds":
        """Update with likelihood ratio P(evidence|H1)/P(evidence|H0)."""
        lr = max(1e-10, lr)
        return LogOdds(log_odds=self.log_odds + math.log(lr))


@dataclass
class FuzzyValue:
    """A fuzzy value with membership degree."""
    value: Any
    membership: float  # [0, 1] membership degree
    label: str = ""
    
    def __post_init__(self):
        self.membership = max(0.0, min(1.0, self.membership))


class FuzzyMembershipFunction(ABC):
    """Abstract base for fuzzy membership functions."""
    
    @abstractmethod
    def evaluate(self, x: float) -> float:
        """Evaluate membership degree for value x."""
        pass
    
    @abstractmethod
    def centroid(self) -> float:
        """Return the centroid of this membership function."""
        pass


class TriangularMembership(FuzzyMembershipFunction):
    """Triangular fuzzy membership function."""
    
    def __init__(self, left: float, center: float, right: float):
        self.left = left
        self.center = center
        self.right = right
    
    def evaluate(self, x: float) -> float:
        if x <= self.left or x >= self.right:
            return 0.0
        elif x <= self.center:
            return (x - self.left) / (self.center - self.left)
        else:
            return (self.right - x) / (self.right - self.center)
    
    def centroid(self) -> float:
        return self.center


class TrapezoidalMembership(FuzzyMembershipFunction):
    """Trapezoidal fuzzy membership function."""
    
    def __init__(self, a: float, b: float, c: float, d: float):
        self.a = a  # Left foot
        self.b = b  # Left shoulder
        self.c = c  # Right shoulder
        self.d = d  # Right foot
    
    def evaluate(self, x: float) -> float:
        if x <= self.a or x >= self.d:
            return 0.0
        elif x <= self.b:
            return (x - self.a) / (self.b - self.a) if self.b > self.a else 1.0
        elif x <= self.c:
            return 1.0
        else:
            return (self.d - x) / (self.d - self.c) if self.d > self.c else 1.0
    
    def centroid(self) -> float:
        return (self.b + self.c) / 2


class GaussianMembership(FuzzyMembershipFunction):
    """Gaussian fuzzy membership function."""
    
    def __init__(self, mean: float, std: float):
        self.mean = mean
        self.std = max(0.001, std)
    
    def evaluate(self, x: float) -> float:
        return math.exp(-0.5 * ((x - self.mean) / self.std) ** 2)
    
    def centroid(self) -> float:
        return self.mean


class SigmoidMembership(FuzzyMembershipFunction):
    """Sigmoid fuzzy membership function."""
    
    def __init__(self, center: float, slope: float):
        self.center = center
        self.slope = slope
    
    def evaluate(self, x: float) -> float:
        return 1 / (1 + math.exp(-self.slope * (x - self.center)))
    
    def centroid(self) -> float:
        return self.center


@dataclass
class FuzzyVariable:
    """A fuzzy linguistic variable."""
    name: str
    universe: Tuple[float, float]  # Min, max range
    terms: Dict[str, FuzzyMembershipFunction] = field(default_factory=dict)
    
    def add_term(self, label: str, mf: FuzzyMembershipFunction) -> None:
        """Add a linguistic term."""
        self.terms[label] = mf
    
    def fuzzify(self, value: float) -> Dict[str, float]:
        """Fuzzify a crisp value into membership degrees."""
        return {
            label: mf.evaluate(value)
            for label, mf in self.terms.items()
        }
    
    def defuzzify_centroid(self, memberships: Dict[str, float]) -> float:
        """Defuzzify using centroid method."""
        num = 0.0
        denom = 0.0
        for label, membership in memberships.items():
            if label in self.terms:
                centroid = self.terms[label].centroid()
                num += centroid * membership
                denom += membership
        
        return num / denom if denom > 0 else (self.universe[0] + self.universe[1]) / 2


@dataclass
class FuzzyRule:
    """A fuzzy inference rule."""
    rule_id: str
    antecedents: Dict[str, str]  # variable_name -> term_label
    consequent_var: str
    consequent_term: str
    weight: float = 1.0
    
    def evaluate_antecedent(
        self,
        fuzzy_inputs: Dict[str, Dict[str, float]]
    ) -> float:
        """Evaluate firing strength of antecedent."""
        # Use minimum (AND) for combining antecedents
        strengths = []
        for var_name, term in self.antecedents.items():
            if var_name in fuzzy_inputs and term in fuzzy_inputs[var_name]:
                strengths.append(fuzzy_inputs[var_name][term])
            else:
                strengths.append(0.0)
        
        if not strengths:
            return 0.0
        
        return min(strengths) * self.weight


class FuzzyInferenceEngine:
    """Mamdani-style fuzzy inference engine."""
    
    def __init__(self):
        self.variables: Dict[str, FuzzyVariable] = {}
        self.rules: List[FuzzyRule] = []
    
    def add_variable(self, variable: FuzzyVariable) -> None:
        """Add a fuzzy variable."""
        self.variables[variable.name] = variable
    
    def add_rule(self, rule: FuzzyRule) -> None:
        """Add a fuzzy rule."""
        self.rules.append(rule)
    
    def infer(
        self,
        inputs: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Perform fuzzy inference.
        
        Args:
            inputs: Crisp input values {variable_name: value}
        
        Returns:
            Defuzzified output values
        """
        # Step 1: Fuzzify inputs
        fuzzy_inputs = {}
        for var_name, value in inputs.items():
            if var_name in self.variables:
                fuzzy_inputs[var_name] = self.variables[var_name].fuzzify(value)
        
        # Step 2: Evaluate rules
        consequent_activations: Dict[str, Dict[str, float]] = {}
        
        for rule in self.rules:
            firing_strength = rule.evaluate_antecedent(fuzzy_inputs)
            
            if firing_strength > 0:
                if rule.consequent_var not in consequent_activations:
                    consequent_activations[rule.consequent_var] = {}
                
                current = consequent_activations[rule.consequent_var].get(
                    rule.consequent_term, 0.0
                )
                # Max aggregation
                consequent_activations[rule.consequent_var][rule.consequent_term] = max(
                    current, firing_strength
                )
        
        # Step 3: Defuzzify outputs
        outputs = {}
        for var_name, activations in consequent_activations.items():
            if var_name in self.variables:
                outputs[var_name] = self.variables[var_name].defuzzify_centroid(activations)
        
        return outputs


@dataclass
class ProbabilisticStatement:
    """A statement with probabilistic confidence."""
    statement: str
    prior: LogOdds
    posterior: Optional[LogOdds] = None
    evidence: List[str] = field(default_factory=list)
    confidence_interval: Optional[ConfidenceInterval] = None
    
    @property
    def probability(self) -> float:
        """Current probability (posterior if available)."""
        odds = self.posterior or self.prior
        return odds.to_probability()
    
    def update_with_evidence(
        self,
        evidence_desc: str,
        likelihood_ratio: float
    ) -> "ProbabilisticStatement":
        """Update belief with new evidence."""
        current = self.posterior or self.prior
        new_posterior = current.update_with_likelihood_ratio(likelihood_ratio)
        
        return ProbabilisticStatement(
            statement=self.statement,
            prior=self.prior,
            posterior=new_posterior,
            evidence=self.evidence + [evidence_desc],
            confidence_interval=self._compute_interval(new_posterior)
        )
    
    def _compute_interval(self, odds: LogOdds) -> ConfidenceInterval:
        """Compute confidence interval around point estimate."""
        p = odds.to_probability()
        # Simple approximation using logit transformation
        # Width decreases with more evidence
        n = len(self.evidence) + 1
        half_width = 1.96 / math.sqrt(n + 1) * 0.5  # Simplified
        
        return ConfidenceInterval(
            lower=max(0, p - half_width),
            point=p,
            upper=min(1, p + half_width)
        )


@dataclass
class SoftConstraintResult:
    """Result of soft constraint evaluation."""
    constraint_id: str
    satisfaction_degree: float  # [0, 1] instead of boolean
    penalty: float  # Cost of partial satisfaction
    confidence: ConfidenceInterval
    details: str


class SoftConstraintEvaluator:
    """Evaluates constraints with fuzzy/soft satisfaction."""
    
    def __init__(self):
        self._constraints: Dict[str, Callable[[Dict[str, Any]], float]] = {}
        self._weights: Dict[str, float] = {}
    
    def add_constraint(
        self,
        constraint_id: str,
        evaluator: Callable[[Dict[str, Any]], float],
        weight: float = 1.0
    ) -> None:
        """
        Add a soft constraint.
        
        evaluator should return satisfaction degree in [0, 1]
        """
        self._constraints[constraint_id] = evaluator
        self._weights[constraint_id] = weight
    
    def evaluate(
        self,
        context: Dict[str, Any]
    ) -> Tuple[float, List[SoftConstraintResult]]:
        """
        Evaluate all constraints softly.
        
        Returns overall satisfaction and individual results.
        """
        results = []
        total_weight = sum(self._weights.values())
        weighted_satisfaction = 0.0
        
        for cid, evaluator in self._constraints.items():
            try:
                satisfaction = evaluator(context)
                satisfaction = max(0.0, min(1.0, satisfaction))
            except Exception:
                satisfaction = 0.0
            
            weight = self._weights[cid]
            penalty = (1.0 - satisfaction) * weight
            
            # Estimate confidence based on satisfaction
            half_width = 0.1 * (1.0 - satisfaction + 0.1)
            confidence = ConfidenceInterval(
                lower=max(0, satisfaction - half_width),
                point=satisfaction,
                upper=min(1, satisfaction + half_width)
            )
            
            results.append(SoftConstraintResult(
                constraint_id=cid,
                satisfaction_degree=satisfaction,
                penalty=penalty,
                confidence=confidence,
                details=f"Satisfaction: {satisfaction:.2%}"
            ))
            
            weighted_satisfaction += satisfaction * weight
        
        overall = weighted_satisfaction / total_weight if total_weight > 0 else 1.0
        
        return overall, results


class BayesianBeliefTracker:
    """Tracks beliefs using Bayesian updates."""
    
    def __init__(self, default_prior: float = 0.5):
        self._beliefs: Dict[str, ProbabilisticStatement] = {}
        self._default_prior = default_prior
    
    def initialize_belief(
        self,
        statement: str,
        prior: float = None
    ) -> ProbabilisticStatement:
        """Initialize a belief with prior probability."""
        prior = prior or self._default_prior
        belief = ProbabilisticStatement(
            statement=statement,
            prior=LogOdds.from_probability(prior)
        )
        self._beliefs[statement] = belief
        return belief
    
    def update_belief(
        self,
        statement: str,
        evidence: str,
        supports: bool,
        strength: float = 2.0
    ) -> ProbabilisticStatement:
        """
        Update belief with evidence.
        
        Args:
            statement: The belief statement
            evidence: Description of evidence
            supports: Whether evidence supports (True) or contradicts (False)
            strength: Likelihood ratio magnitude (>1 = strong evidence)
        """
        if statement not in self._beliefs:
            self.initialize_belief(statement)
        
        belief = self._beliefs[statement]
        
        # Compute likelihood ratio
        lr = strength if supports else 1.0 / strength
        
        updated = belief.update_with_evidence(evidence, lr)
        self._beliefs[statement] = updated
        
        return updated
    
    def get_belief(self, statement: str) -> Optional[ProbabilisticStatement]:
        """Get current belief state."""
        return self._beliefs.get(statement)
    
    def get_all_beliefs(self) -> Dict[str, float]:
        """Get all beliefs as probabilities."""
        return {
            stmt: belief.probability
            for stmt, belief in self._beliefs.items()
        }


@dataclass
class UncertaintyBand:
    """Uncertainty band for output values."""
    value: float
    lower_bound: float
    upper_bound: float
    uncertainty_type: str  # "epistemic", "aleatoric", "combined"
    sources: List[str] = field(default_factory=list)
    
    @property
    def spread(self) -> float:
        """Spread/width of uncertainty."""
        return self.upper_bound - self.lower_bound
    
    def is_confident(self, threshold: float = 0.2) -> bool:
        """Check if uncertainty is below threshold."""
        return self.spread < threshold


class StructuredUncertaintyTracker:
    """
    Tracks structured uncertainty through inference chains.
    
    Propagates uncertainty bands through computations.
    """
    
    def __init__(self):
        self._values: Dict[str, UncertaintyBand] = {}
    
    def set_value(
        self,
        key: str,
        value: float,
        uncertainty: float,
        uncertainty_type: str = "combined",
        source: str = ""
    ) -> UncertaintyBand:
        """Set a value with uncertainty."""
        band = UncertaintyBand(
            value=value,
            lower_bound=value - uncertainty,
            upper_bound=value + uncertainty,
            uncertainty_type=uncertainty_type,
            sources=[source] if source else []
        )
        self._values[key] = band
        return band
    
    def propagate_sum(
        self,
        result_key: str,
        operand_keys: List[str]
    ) -> UncertaintyBand:
        """Propagate uncertainty through summation."""
        values = []
        lower = 0.0
        upper = 0.0
        sources = []
        
        for key in operand_keys:
            if key in self._values:
                band = self._values[key]
                values.append(band.value)
                # Sum uncertainties (assuming independence)
                lower += band.lower_bound
                upper += band.upper_bound
                sources.extend(band.sources)
        
        result = UncertaintyBand(
            value=sum(values),
            lower_bound=lower,
            upper_bound=upper,
            uncertainty_type="propagated",
            sources=sources
        )
        self._values[result_key] = result
        return result
    
    def propagate_product(
        self,
        result_key: str,
        operand_keys: List[str]
    ) -> UncertaintyBand:
        """Propagate uncertainty through multiplication."""
        value = 1.0
        relative_uncertainties = []
        sources = []
        
        for key in operand_keys:
            if key in self._values:
                band = self._values[key]
                value *= band.value
                if band.value != 0:
                    rel_unc = band.spread / (2 * abs(band.value))
                    relative_uncertainties.append(rel_unc)
                sources.extend(band.sources)
        
        # Combine relative uncertainties in quadrature
        combined_rel = math.sqrt(sum(r**2 for r in relative_uncertainties))
        abs_unc = abs(value) * combined_rel
        
        result = UncertaintyBand(
            value=value,
            lower_bound=value - abs_unc,
            upper_bound=value + abs_unc,
            uncertainty_type="propagated",
            sources=sources
        )
        self._values[result_key] = result
        return result
    
    def get_value(self, key: str) -> Optional[UncertaintyBand]:
        """Get a value with its uncertainty."""
        return self._values.get(key)
    
    def is_confident(self, key: str, threshold: float = 0.2) -> bool:
        """Check if a value's uncertainty is below threshold."""
        band = self._values.get(key)
        if band:
            return band.is_confident(threshold)
        return False


# Convenience functions

def create_fuzzy_risk_variable() -> FuzzyVariable:
    """Create a standard fuzzy variable for risk assessment."""
    risk = FuzzyVariable("risk", universe=(0.0, 1.0))
    risk.add_term("low", TrapezoidalMembership(0.0, 0.0, 0.2, 0.35))
    risk.add_term("medium", TriangularMembership(0.25, 0.5, 0.75))
    risk.add_term("high", TrapezoidalMembership(0.65, 0.8, 1.0, 1.0))
    return risk


def create_fuzzy_confidence_variable() -> FuzzyVariable:
    """Create a standard fuzzy variable for confidence."""
    conf = FuzzyVariable("confidence", universe=(0.0, 1.0))
    conf.add_term("very_low", TrapezoidalMembership(0.0, 0.0, 0.15, 0.25))
    conf.add_term("low", TriangularMembership(0.15, 0.3, 0.45))
    conf.add_term("medium", TriangularMembership(0.35, 0.5, 0.65))
    conf.add_term("high", TriangularMembership(0.55, 0.7, 0.85))
    conf.add_term("very_high", TrapezoidalMembership(0.75, 0.85, 1.0, 1.0))
    return conf


def bayesian_update(prior: float, likelihood_ratio: float) -> float:
    """Simple Bayesian update returning posterior probability."""
    odds = LogOdds.from_probability(prior)
    updated = odds.update_with_likelihood_ratio(likelihood_ratio)
    return updated.to_probability()


def combine_intervals(
    intervals: List[ConfidenceInterval]
) -> ConfidenceInterval:
    """Combine multiple confidence intervals."""
    if not intervals:
        return ConfidenceInterval(lower=0.5, point=0.5, upper=0.5)
    
    result = intervals[0]
    for interval in intervals[1:]:
        result = result.combine_with(interval)
    
    return result
