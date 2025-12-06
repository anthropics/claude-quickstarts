"""
Uncertainty and Abstention System - Phase 2

Implements:
- Confidence calibration with honest uncertainty
- Abstention when confidence is too low
- "I don't know" responses when appropriate
- Grounding confidence in token probabilities where possible
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math


class ConfidenceSource(Enum):
    """Sources of confidence estimation."""
    MODEL_LOGPROBS = "model_logprobs"  # From token probabilities
    SELF_ASSESSMENT = "self_assessment"  # Self-reported confidence
    CALIBRATION = "calibration"  # Calibrated from history
    ENSEMBLE = "ensemble"  # Multiple model agreement
    CRITIC = "critic"  # From critic system
    HYBRID = "hybrid"  # Combined sources


class UncertaintyType(Enum):
    """Types of uncertainty."""
    EPISTEMIC = "epistemic"  # Knowledge uncertainty (reducible)
    ALEATORIC = "aleatoric"  # Inherent randomness (irreducible)
    MODEL = "model"  # Model limitation
    DATA = "data"  # Insufficient data/context
    AMBIGUITY = "ambiguity"  # Ambiguous input


class AbstentionReason(Enum):
    """Reasons for abstaining from an answer."""
    LOW_CONFIDENCE = "low_confidence"
    INSUFFICIENT_DATA = "insufficient_data"
    OUT_OF_SCOPE = "out_of_scope"
    AMBIGUOUS_QUERY = "ambiguous_query"
    HARMFUL_CONTENT = "harmful_content"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    REQUIRES_EXPERTISE = "requires_expertise"


@dataclass
class ConfidenceEstimate:
    """A calibrated confidence estimate."""
    value: float  # 0-1 probability
    source: ConfidenceSource
    uncertainty_type: Optional[UncertaintyType] = None
    lower_bound: Optional[float] = None  # Confidence interval
    upper_bound: Optional[float] = None
    explanation: str = ""
    factors: Dict[str, float] = field(default_factory=dict)
    
    @property
    def interval_width(self) -> float:
        """Width of confidence interval."""
        if self.lower_bound is not None and self.upper_bound is not None:
            return self.upper_bound - self.lower_bound
        return 0.0
    
    def is_reliable(self, threshold: float = 0.5) -> bool:
        """Check if confidence is reliable enough."""
        return self.value >= threshold and self.interval_width < 0.3


@dataclass
class AbstentionDecision:
    """Decision about whether to abstain."""
    should_abstain: bool
    reason: Optional[AbstentionReason] = None
    confidence: float = 0.0
    alternative_response: Optional[str] = None
    follow_up_questions: List[str] = field(default_factory=list)
    explanation: str = ""


@dataclass
class CalibrationData:
    """Historical data for calibration."""
    predicted_confidence: float
    actual_correct: bool
    timestamp: str
    domain: Optional[str] = None


class ConfidenceCalibrator:
    """
    Calibrates confidence estimates based on historical accuracy.
    
    Uses Platt scaling or similar methods to map raw confidence
    to calibrated probabilities.
    """
    
    def __init__(self, window_size: int = 1000):
        self.history: List[CalibrationData] = []
        self.window_size = window_size
        
        # Calibration parameters (Platt scaling)
        self.a: float = 1.0  # Slope
        self.b: float = 0.0  # Intercept
        
        # Bin statistics for reliability diagram
        self.bins: Dict[int, Dict[str, float]] = {
            i: {"total": 0, "correct": 0}
            for i in range(10)
        }
    
    def record(
        self,
        predicted: float,
        actual_correct: bool,
        domain: Optional[str] = None
    ) -> None:
        """Record a prediction for calibration."""
        self.history.append(CalibrationData(
            predicted_confidence=predicted,
            actual_correct=actual_correct,
            timestamp=datetime.now().isoformat(),
            domain=domain
        ))
        
        # Update bin statistics
        bin_idx = min(9, int(predicted * 10))
        self.bins[bin_idx]["total"] += 1
        if actual_correct:
            self.bins[bin_idx]["correct"] += 1
        
        # Maintain window
        if len(self.history) > self.window_size:
            self.history = self.history[-self.window_size:]
            self._recalculate_bins()
        
        # Periodically recalibrate
        if len(self.history) % 100 == 0:
            self._fit_calibration()
    
    def calibrate(self, raw_confidence: float) -> float:
        """Apply calibration to raw confidence."""
        # Platt scaling: calibrated = sigmoid(a * raw + b)
        z = self.a * raw_confidence + self.b
        calibrated = 1 / (1 + math.exp(-z))
        
        # Ensure bounds
        return max(0.01, min(0.99, calibrated))
    
    def get_calibration_error(self) -> float:
        """Calculate Expected Calibration Error (ECE)."""
        total_samples = sum(b["total"] for b in self.bins.values())
        if total_samples == 0:
            return 0.0
        
        ece = 0.0
        for bin_idx, stats in self.bins.items():
            if stats["total"] > 0:
                bin_confidence = (bin_idx + 0.5) / 10
                bin_accuracy = stats["correct"] / stats["total"]
                weight = stats["total"] / total_samples
                ece += weight * abs(bin_accuracy - bin_confidence)
        
        return ece
    
    def get_reliability_diagram(self) -> Dict[str, Any]:
        """Get data for reliability diagram."""
        confidences = []
        accuracies = []
        counts = []
        
        for bin_idx in range(10):
            stats = self.bins[bin_idx]
            confidences.append((bin_idx + 0.5) / 10)
            if stats["total"] > 0:
                accuracies.append(stats["correct"] / stats["total"])
            else:
                accuracies.append(0.0)
            counts.append(stats["total"])
        
        return {
            "confidences": confidences,
            "accuracies": accuracies,
            "counts": counts,
            "ece": self.get_calibration_error()
        }
    
    def _fit_calibration(self) -> None:
        """Fit calibration parameters using Platt scaling."""
        if len(self.history) < 50:
            return
        
        # Simple gradient descent for Platt scaling
        lr = 0.01
        for _ in range(100):
            grad_a = 0.0
            grad_b = 0.0
            
            for data in self.history:
                z = self.a * data.predicted_confidence + self.b
                p = 1 / (1 + math.exp(-z))
                y = 1.0 if data.actual_correct else 0.0
                
                error = p - y
                grad_a += error * data.predicted_confidence
                grad_b += error
            
            self.a -= lr * grad_a / len(self.history)
            self.b -= lr * grad_b / len(self.history)
    
    def _recalculate_bins(self) -> None:
        """Recalculate bin statistics from history."""
        self.bins = {
            i: {"total": 0, "correct": 0}
            for i in range(10)
        }
        
        for data in self.history:
            bin_idx = min(9, int(data.predicted_confidence * 10))
            self.bins[bin_idx]["total"] += 1
            if data.actual_correct:
                self.bins[bin_idx]["correct"] += 1


class UncertaintyEstimator:
    """
    Estimates uncertainty from various sources.
    """
    
    def __init__(self):
        self.calibrator = ConfidenceCalibrator()
    
    def estimate_from_logprobs(
        self,
        token_logprobs: List[float],
        key_token_indices: Optional[List[int]] = None
    ) -> ConfidenceEstimate:
        """Estimate confidence from token log probabilities."""
        if not token_logprobs:
            return ConfidenceEstimate(
                value=0.5,
                source=ConfidenceSource.MODEL_LOGPROBS,
                explanation="No log probabilities available"
            )
        
        # Use key tokens if specified, otherwise all tokens
        if key_token_indices:
            relevant_probs = [token_logprobs[i] for i in key_token_indices 
                             if i < len(token_logprobs)]
        else:
            relevant_probs = token_logprobs
        
        # Convert log probs to probabilities
        probs = [math.exp(lp) for lp in relevant_probs]
        
        # Aggregate (geometric mean for sequence probability)
        if probs:
            geo_mean = math.exp(sum(math.log(p) for p in probs) / len(probs))
        else:
            geo_mean = 0.5
        
        # Calculate variance for uncertainty interval
        if len(probs) > 1:
            variance = sum((p - geo_mean) ** 2 for p in probs) / len(probs)
            std_dev = math.sqrt(variance)
        else:
            std_dev = 0.1
        
        return ConfidenceEstimate(
            value=self.calibrator.calibrate(geo_mean),
            source=ConfidenceSource.MODEL_LOGPROBS,
            uncertainty_type=UncertaintyType.MODEL,
            lower_bound=max(0, geo_mean - 2 * std_dev),
            upper_bound=min(1, geo_mean + 2 * std_dev),
            explanation=f"Based on {len(probs)} token probabilities",
            factors={"mean_prob": geo_mean, "std_dev": std_dev}
        )
    
    def estimate_from_self_assessment(
        self,
        self_reported: float,
        reasoning_length: int,
        has_hedging: bool,
        has_citations: bool
    ) -> ConfidenceEstimate:
        """Estimate confidence from self-assessment factors."""
        # Start with self-reported confidence
        confidence = self_reported
        
        # Adjust based on factors
        factors = {
            "self_reported": self_reported,
            "reasoning_length": 0.0,
            "hedging_penalty": 0.0,
            "citation_bonus": 0.0
        }
        
        # Longer reasoning often correlates with lower confidence
        if reasoning_length > 500:
            penalty = min(0.1, (reasoning_length - 500) / 5000)
            confidence -= penalty
            factors["reasoning_length"] = -penalty
        
        # Hedging language reduces confidence
        if has_hedging:
            confidence -= 0.15
            factors["hedging_penalty"] = -0.15
        
        # Citations increase confidence
        if has_citations:
            confidence += 0.1
            factors["citation_bonus"] = 0.1
        
        confidence = max(0.1, min(0.95, confidence))
        
        return ConfidenceEstimate(
            value=self.calibrator.calibrate(confidence),
            source=ConfidenceSource.SELF_ASSESSMENT,
            uncertainty_type=UncertaintyType.EPISTEMIC,
            explanation="Based on self-assessment with adjustments",
            factors=factors
        )
    
    def estimate_from_ensemble(
        self,
        responses: List[str],
        confidences: List[float]
    ) -> ConfidenceEstimate:
        """Estimate confidence from ensemble of responses."""
        if not responses or not confidences:
            return ConfidenceEstimate(
                value=0.5,
                source=ConfidenceSource.ENSEMBLE,
                explanation="No ensemble data available"
            )
        
        # Calculate agreement
        n = len(responses)
        agreement = self._calculate_agreement(responses)
        
        # Combine agreement with average confidence
        avg_conf = sum(confidences) / len(confidences)
        conf_std = math.sqrt(sum((c - avg_conf) ** 2 for c in confidences) / n) if n > 1 else 0
        
        # Higher agreement = higher confidence
        combined = avg_conf * (0.5 + 0.5 * agreement)
        
        return ConfidenceEstimate(
            value=self.calibrator.calibrate(combined),
            source=ConfidenceSource.ENSEMBLE,
            uncertainty_type=UncertaintyType.EPISTEMIC,
            lower_bound=max(0, combined - 2 * conf_std),
            upper_bound=min(1, combined + 2 * conf_std),
            explanation=f"Ensemble of {n} responses with {agreement:.0%} agreement",
            factors={
                "agreement": agreement,
                "avg_confidence": avg_conf,
                "confidence_std": conf_std
            }
        )
    
    def combine_estimates(
        self,
        estimates: List[ConfidenceEstimate],
        weights: Optional[List[float]] = None
    ) -> ConfidenceEstimate:
        """Combine multiple confidence estimates."""
        if not estimates:
            return ConfidenceEstimate(
                value=0.5,
                source=ConfidenceSource.HYBRID,
                explanation="No estimates to combine"
            )
        
        if weights is None:
            weights = [1.0] * len(estimates)
        
        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        # Weighted average
        combined_value = sum(e.value * w for e, w in zip(estimates, weights))
        
        # Combine intervals
        lower_bounds = [e.lower_bound for e in estimates if e.lower_bound is not None]
        upper_bounds = [e.upper_bound for e in estimates if e.upper_bound is not None]
        
        return ConfidenceEstimate(
            value=combined_value,
            source=ConfidenceSource.HYBRID,
            lower_bound=min(lower_bounds) if lower_bounds else None,
            upper_bound=max(upper_bounds) if upper_bounds else None,
            explanation=f"Combined from {len(estimates)} sources",
            factors={
                e.source.value: e.value
                for e in estimates
            }
        )
    
    def _calculate_agreement(self, responses: List[str]) -> float:
        """Calculate agreement between responses."""
        if len(responses) < 2:
            return 1.0
        
        # Simple word overlap based agreement
        total_pairs = 0
        agreement_sum = 0.0
        
        for i in range(len(responses)):
            words_i = set(responses[i].lower().split())
            for j in range(i + 1, len(responses)):
                words_j = set(responses[j].lower().split())
                
                if not words_i or not words_j:
                    continue
                
                overlap = len(words_i & words_j)
                union = len(words_i | words_j)
                
                agreement_sum += overlap / union if union > 0 else 0
                total_pairs += 1
        
        return agreement_sum / total_pairs if total_pairs > 0 else 0.0


class AbstentionPolicy:
    """
    Policy for deciding when to abstain from answering.
    """
    
    def __init__(
        self,
        confidence_threshold: float = 0.4,
        uncertainty_threshold: float = 0.3,
        require_grounding: bool = True
    ):
        self.confidence_threshold = confidence_threshold
        self.uncertainty_threshold = uncertainty_threshold
        self.require_grounding = require_grounding
        
        # Track abstention statistics
        self.abstention_count = 0
        self.total_queries = 0
        self.abstention_reasons: Dict[str, int] = {}
    
    def should_abstain(
        self,
        confidence: ConfidenceEstimate,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AbstentionDecision:
        """Decide whether to abstain from answering."""
        self.total_queries += 1
        context = context or {}
        
        # Check confidence threshold
        if confidence.value < self.confidence_threshold:
            self._record_abstention(AbstentionReason.LOW_CONFIDENCE)
            return AbstentionDecision(
                should_abstain=True,
                reason=AbstentionReason.LOW_CONFIDENCE,
                confidence=confidence.value,
                alternative_response=self._generate_low_confidence_response(confidence),
                explanation=f"Confidence {confidence.value:.0%} below threshold {self.confidence_threshold:.0%}"
            )
        
        # Check uncertainty interval
        if confidence.interval_width > self.uncertainty_threshold:
            self._record_abstention(AbstentionReason.CONFLICTING_EVIDENCE)
            return AbstentionDecision(
                should_abstain=True,
                reason=AbstentionReason.CONFLICTING_EVIDENCE,
                confidence=confidence.value,
                alternative_response="I have conflicting information about this topic.",
                follow_up_questions=["Could you provide more context?"],
                explanation=f"Uncertainty interval {confidence.interval_width:.0%} too wide"
            )
        
        # Check for ambiguous query
        if self._is_ambiguous(query):
            self._record_abstention(AbstentionReason.AMBIGUOUS_QUERY)
            return AbstentionDecision(
                should_abstain=True,
                reason=AbstentionReason.AMBIGUOUS_QUERY,
                confidence=confidence.value,
                alternative_response="Your question could be interpreted in multiple ways.",
                follow_up_questions=self._generate_clarifying_questions(query),
                explanation="Query is ambiguous"
            )
        
        # Check for out-of-scope
        domain = context.get("domain")
        if domain and not self._in_scope(query, domain):
            self._record_abstention(AbstentionReason.OUT_OF_SCOPE)
            return AbstentionDecision(
                should_abstain=True,
                reason=AbstentionReason.OUT_OF_SCOPE,
                confidence=confidence.value,
                alternative_response=f"This question is outside my expertise in {domain}.",
                explanation=f"Query outside {domain} domain"
            )
        
        # Check for insufficient data
        if context.get("data_available", True) is False:
            self._record_abstention(AbstentionReason.INSUFFICIENT_DATA)
            return AbstentionDecision(
                should_abstain=True,
                reason=AbstentionReason.INSUFFICIENT_DATA,
                confidence=confidence.value,
                alternative_response="I don't have enough information to answer this accurately.",
                follow_up_questions=["What additional context can you provide?"],
                explanation="Insufficient data for reliable answer"
            )
        
        # No abstention needed
        return AbstentionDecision(
            should_abstain=False,
            confidence=confidence.value,
            explanation="Sufficient confidence to proceed"
        )
    
    def _is_ambiguous(self, query: str) -> bool:
        """Check if query is ambiguous."""
        ambiguity_markers = [
            "what do you mean",
            "or something",
            "whatever",
            "you know",
            "like that",
            "stuff like"
        ]
        query_lower = query.lower()
        return any(marker in query_lower for marker in ambiguity_markers)
    
    def _in_scope(self, query: str, domain: str) -> bool:
        """Check if query is in scope for domain."""
        # Simplified scope checking
        domain_keywords = {
            "logic": ["argument", "valid", "fallacy", "premise", "conclusion", "syllogism"],
            "math": ["calculate", "equation", "formula", "solve", "number"],
            "code": ["function", "variable", "error", "debug", "compile"],
        }
        
        if domain in domain_keywords:
            return any(kw in query.lower() for kw in domain_keywords[domain])
        
        return True  # Default to in-scope for unknown domains
    
    def _generate_low_confidence_response(
        self, 
        confidence: ConfidenceEstimate
    ) -> str:
        """Generate appropriate response for low confidence."""
        if confidence.value < 0.2:
            return "I don't know the answer to this question."
        elif confidence.value < 0.3:
            return "I'm not confident I can answer this accurately."
        else:
            return f"I'm only {confidence.value:.0%} confident about this, which may not be reliable."
    
    def _generate_clarifying_questions(self, query: str) -> List[str]:
        """Generate questions to clarify ambiguous query."""
        return [
            "Could you be more specific about what you're asking?",
            "What context or domain does this relate to?",
            "Are you asking about [X] or [Y]?"
        ]
    
    def _record_abstention(self, reason: AbstentionReason) -> None:
        """Record an abstention for statistics."""
        self.abstention_count += 1
        reason_str = reason.value
        self.abstention_reasons[reason_str] = \
            self.abstention_reasons.get(reason_str, 0) + 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get abstention statistics."""
        return {
            "total_queries": self.total_queries,
            "abstention_count": self.abstention_count,
            "abstention_rate": self.abstention_count / self.total_queries if self.total_queries > 0 else 0,
            "reasons": self.abstention_reasons
        }


class UncertaintySystem:
    """
    Complete uncertainty and abstention system.
    """
    
    def __init__(
        self,
        confidence_threshold: float = 0.4,
        calibration_window: int = 1000
    ):
        self.estimator = UncertaintyEstimator()
        self.estimator.calibrator = ConfidenceCalibrator(calibration_window)
        self.policy = AbstentionPolicy(confidence_threshold=confidence_threshold)
    
    def assess(
        self,
        query: str,
        response: str,
        token_logprobs: Optional[List[float]] = None,
        self_reported_confidence: float = 0.7,
        ensemble_responses: Optional[List[str]] = None,
        ensemble_confidences: Optional[List[float]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Full uncertainty assessment for a response.
        
        Returns confidence estimate and abstention decision.
        """
        estimates = []
        
        # Get logprob-based estimate if available
        if token_logprobs:
            estimates.append(self.estimator.estimate_from_logprobs(token_logprobs))
        
        # Get self-assessment estimate
        has_hedging = any(h in response.lower() for h in 
                        ["might", "perhaps", "possibly", "not sure", "uncertain"])
        has_citations = "[" in response or "according to" in response.lower()
        
        estimates.append(self.estimator.estimate_from_self_assessment(
            self_reported_confidence,
            len(response),
            has_hedging,
            has_citations
        ))
        
        # Get ensemble estimate if available
        if ensemble_responses and ensemble_confidences:
            estimates.append(self.estimator.estimate_from_ensemble(
                ensemble_responses,
                ensemble_confidences
            ))
        
        # Combine estimates
        confidence = self.estimator.combine_estimates(estimates)
        
        # Check abstention policy
        abstention = self.policy.should_abstain(confidence, query, context)
        
        return {
            "confidence": {
                "value": confidence.value,
                "source": confidence.source.value,
                "interval": [confidence.lower_bound, confidence.upper_bound],
                "explanation": confidence.explanation,
                "factors": confidence.factors
            },
            "abstention": {
                "should_abstain": abstention.should_abstain,
                "reason": abstention.reason.value if abstention.reason else None,
                "alternative_response": abstention.alternative_response,
                "follow_up_questions": abstention.follow_up_questions
            },
            "recommendation": self._generate_recommendation(confidence, abstention)
        }
    
    def record_outcome(
        self,
        predicted_confidence: float,
        was_correct: bool,
        domain: Optional[str] = None
    ) -> None:
        """Record outcome for calibration."""
        self.estimator.calibrator.record(predicted_confidence, was_correct, domain)
    
    def get_calibration_report(self) -> Dict[str, Any]:
        """Get calibration statistics."""
        return {
            "calibration": self.estimator.calibrator.get_reliability_diagram(),
            "abstention": self.policy.get_statistics()
        }
    
    def _generate_recommendation(
        self,
        confidence: ConfidenceEstimate,
        abstention: AbstentionDecision
    ) -> str:
        """Generate recommendation based on assessment."""
        if abstention.should_abstain:
            return f"ABSTAIN: {abstention.explanation}"
        elif confidence.value >= 0.8:
            return "PROCEED: High confidence response"
        elif confidence.value >= 0.6:
            return "PROCEED_WITH_CAVEAT: Add uncertainty language"
        else:
            return "PROCEED_CAREFULLY: Consider adding disclaimers"
