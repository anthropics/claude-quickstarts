"""
Source Trust Calibration System - Advanced Enhancement

Provides source reliability and recency modeling:
- Source reputation tracking
- Temporal decay for recency
- Trust propagation through citations
- Conflict resolution for contradicting sources
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import math


class TrustLevel(Enum):
    """Levels of source trust."""
    VERIFIED = "verified"  # Highly trusted, verified source
    TRUSTED = "trusted"  # Generally reliable
    NEUTRAL = "neutral"  # Unknown or mixed reliability
    QUESTIONABLE = "questionable"  # Some credibility issues
    UNTRUSTED = "untrusted"  # Known unreliable


class SourceCategory(Enum):
    """Categories of information sources."""
    ACADEMIC = "academic"  # Peer-reviewed, scholarly
    OFFICIAL = "official"  # Government, institutional
    PROFESSIONAL = "professional"  # Industry, expert
    NEWS = "news"  # Journalism, media
    COMMUNITY = "community"  # User-generated, forums
    UNKNOWN = "unknown"


@dataclass
class Source:
    """An information source with trust attributes."""
    source_id: str
    name: str
    category: SourceCategory
    url: Optional[str] = None
    
    # Trust metrics
    base_trust: float = 0.5  # Prior trust [0, 1]
    verified: bool = False
    verification_date: Optional[datetime] = None
    
    # Track record
    correct_count: int = 0
    incorrect_count: int = 0
    total_citations: int = 0
    
    # Metadata
    domain: str = ""
    established_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    description: str = ""
    
    # Relationships
    cited_sources: Set[str] = field(default_factory=set)
    cited_by: Set[str] = field(default_factory=set)
    
    @property
    def accuracy_rate(self) -> float:
        """Compute accuracy rate from track record."""
        total = self.correct_count + self.incorrect_count
        if total == 0:
            return self.base_trust
        return self.correct_count / total
    
    @property
    def trust_level(self) -> TrustLevel:
        """Determine trust level from score."""
        score = self.accuracy_rate
        if self.verified and score >= 0.9:
            return TrustLevel.VERIFIED
        if score >= 0.75:
            return TrustLevel.TRUSTED
        if score >= 0.5:
            return TrustLevel.NEUTRAL
        if score >= 0.25:
            return TrustLevel.QUESTIONABLE
        return TrustLevel.UNTRUSTED


@dataclass
class Claim:
    """A claim from a source."""
    claim_id: str
    content: str
    source_id: str
    timestamp: datetime
    confidence: float = 1.0
    evidence: List[str] = field(default_factory=list)
    supporting_claims: List[str] = field(default_factory=list)
    contradicting_claims: List[str] = field(default_factory=list)
    verified: Optional[bool] = None


@dataclass
class TrustScore:
    """Computed trust score with breakdown."""
    source_id: str
    total_score: float
    base_component: float
    accuracy_component: float
    recency_component: float
    citation_component: float
    category_component: float
    trust_level: TrustLevel
    explanation: str


@dataclass
class ConflictResolution:
    """Result of resolving conflicting claims."""
    winning_claim: Claim
    confidence: float
    reasoning: str
    supporting_sources: List[str]
    opposing_sources: List[str]
    uncertainty: float


class RecencyDecay(ABC):
    """Abstract base for recency decay functions."""
    
    @abstractmethod
    def compute(self, age: timedelta) -> float:
        """Compute recency factor given age."""


class ExponentialDecay(RecencyDecay):
    """Exponential decay for recency."""
    
    def __init__(self, half_life_days: float = 365.0):
        self.half_life_days = half_life_days
        self.decay_rate = math.log(2) / half_life_days
    
    def compute(self, age: timedelta) -> float:
        """Compute exponential decay factor."""
        days = age.total_seconds() / 86400
        return math.exp(-self.decay_rate * days)


class LinearDecay(RecencyDecay):
    """Linear decay for recency."""
    
    def __init__(self, max_age_days: float = 365.0, min_factor: float = 0.1):
        self.max_age_days = max_age_days
        self.min_factor = min_factor
    
    def compute(self, age: timedelta) -> float:
        """Compute linear decay factor."""
        days = age.total_seconds() / 86400
        if days >= self.max_age_days:
            return self.min_factor
        return 1.0 - (1.0 - self.min_factor) * (days / self.max_age_days)


class StepDecay(RecencyDecay):
    """Step-wise decay for recency."""
    
    def __init__(
        self,
        steps: Optional[List[Tuple[int, float]]] = None
    ):
        # Default steps: (days, factor)
        self.steps = steps or [
            (7, 1.0),      # Within a week
            (30, 0.9),     # Within a month
            (90, 0.7),     # Within 3 months
            (365, 0.5),    # Within a year
            (730, 0.3),    # Within 2 years
        ]
    
    def compute(self, age: timedelta) -> float:
        """Compute step decay factor."""
        days = age.total_seconds() / 86400
        
        for threshold, factor in self.steps:
            if days <= threshold:
                return factor
        
        return 0.1  # Very old


class TrustCalculator:
    """Computes trust scores for sources."""
    
    def __init__(
        self,
        recency_decay: Optional[RecencyDecay] = None,
        category_priors: Optional[Dict[SourceCategory, float]] = None
    ):
        self.recency_decay = recency_decay or ExponentialDecay()
        
        # Default category priors
        self.category_priors = category_priors or {
            SourceCategory.ACADEMIC: 0.85,
            SourceCategory.OFFICIAL: 0.80,
            SourceCategory.PROFESSIONAL: 0.70,
            SourceCategory.NEWS: 0.60,
            SourceCategory.COMMUNITY: 0.40,
            SourceCategory.UNKNOWN: 0.50,
        }
        
        # Weighting for score components
        self.base_weight = 0.15
        self.accuracy_weight = 0.35
        self.recency_weight = 0.20
        self.citation_weight = 0.15
        self.category_weight = 0.15
    
    def compute_trust(
        self,
        source: Source,
        reference_time: Optional[datetime] = None
    ) -> TrustScore:
        """Compute comprehensive trust score."""
        ref_time = reference_time or datetime.now()
        
        # Base component
        base = source.base_trust
        
        # Accuracy component
        accuracy = source.accuracy_rate
        
        # Recency component
        if source.last_updated:
            age = ref_time - source.last_updated
            recency = self.recency_decay.compute(age)
        else:
            recency = 0.5  # Unknown recency
        
        # Citation component (PageRank-like)
        citation_factor = min(math.log(source.total_citations + 1) / 10, 1.0)
        
        # Category prior
        category = self.category_priors.get(source.category, 0.5)
        
        # Weighted combination
        total = (
            self.base_weight * base +
            self.accuracy_weight * accuracy +
            self.recency_weight * recency +
            self.citation_weight * citation_factor +
            self.category_weight * category
        )
        
        # Boost for verified sources
        if source.verified:
            total = min(total * 1.2, 1.0)
        
        # Determine trust level
        if total >= 0.85:
            level = TrustLevel.VERIFIED if source.verified else TrustLevel.TRUSTED
        elif total >= 0.65:
            level = TrustLevel.TRUSTED
        elif total >= 0.45:
            level = TrustLevel.NEUTRAL
        elif total >= 0.25:
            level = TrustLevel.QUESTIONABLE
        else:
            level = TrustLevel.UNTRUSTED
        
        explanation = (
            f"Trust={total:.2f}: base={base:.2f}, accuracy={accuracy:.2f}, "
            f"recency={recency:.2f}, citations={citation_factor:.2f}, "
            f"category={category:.2f}"
        )
        
        return TrustScore(
            source_id=source.source_id,
            total_score=total,
            base_component=base,
            accuracy_component=accuracy,
            recency_component=recency,
            citation_component=citation_factor,
            category_component=category,
            trust_level=level,
            explanation=explanation
        )


class TrustPropagator:
    """Propagates trust through citation networks."""
    
    def __init__(
        self,
        damping_factor: float = 0.85,
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ):
        self.damping_factor = damping_factor
        self.max_iterations = max_iterations
        self.tolerance = tolerance
    
    def propagate(
        self,
        sources: Dict[str, Source]
    ) -> Dict[str, float]:
        """Propagate trust through citation network (PageRank-style)."""
        n = len(sources)
        if n == 0:
            return {}
        
        # Initialize with base trust
        trust = {sid: s.base_trust for sid, s in sources.items()}
        
        for _ in range(self.max_iterations):
            new_trust: Dict[str, float] = {}
            max_delta = 0.0
            
            for sid, source in sources.items():
                # Base trust component
                base = (1 - self.damping_factor) * source.base_trust
                
                # Trust from citing sources
                citation_sum = 0.0
                for citing_id in source.cited_by:
                    if citing_id in sources:
                        citing = sources[citing_id]
                        out_degree = len(citing.cited_sources)
                        if out_degree > 0:
                            citation_sum += trust[citing_id] / out_degree
                
                new_trust[sid] = base + self.damping_factor * citation_sum
                max_delta = max(max_delta, abs(new_trust[sid] - trust[sid]))
            
            trust = new_trust
            
            if max_delta < self.tolerance:
                break
        
        return trust


class ConflictResolver:
    """Resolves conflicts between contradicting claims."""
    
    def __init__(
        self,
        trust_calculator: TrustCalculator,
        recency_weight: float = 0.3
    ):
        self.trust_calculator = trust_calculator
        self.recency_weight = recency_weight
    
    def resolve(
        self,
        claims: List[Claim],
        sources: Dict[str, Source]
    ) -> ConflictResolution:
        """Resolve conflicting claims."""
        if not claims:
            raise ValueError("No claims to resolve")
        
        if len(claims) == 1:
            claim = claims[0]
            return ConflictResolution(
                winning_claim=claim,
                confidence=claim.confidence,
                reasoning="Single claim, no conflict",
                supporting_sources=[claim.source_id],
                opposing_sources=[],
                uncertainty=0.0
            )
        
        # Score each claim
        claim_scores: List[Tuple[Claim, float]] = []
        
        for claim in claims:
            source = sources.get(claim.source_id)
            if not source:
                score = 0.5
            else:
                trust = self.trust_calculator.compute_trust(source)
                score = trust.total_score
            
            # Apply recency boost
            age = datetime.now() - claim.timestamp
            recency_factor = 1.0 / (1.0 + age.days / 365)
            score = score * (1 - self.recency_weight) + recency_factor * self.recency_weight
            
            # Apply claim confidence
            score *= claim.confidence
            
            claim_scores.append((claim, score))
        
        # Sort by score
        claim_scores.sort(key=lambda x: x[1], reverse=True)
        
        winner, winner_score = claim_scores[0]
        runner_up_score = claim_scores[1][1] if len(claim_scores) > 1 else 0.0
        
        # Compute uncertainty
        score_gap = winner_score - runner_up_score
        uncertainty = 1.0 - min(score_gap * 2, 1.0)
        
        # Determine supporting and opposing
        supporting = [c.source_id for c, s in claim_scores if s >= winner_score * 0.9]
        opposing = [c.source_id for c, s in claim_scores if c.claim_id != winner.claim_id]
        
        reasoning = (
            f"Selected claim from {winner.source_id} with score {winner_score:.3f}. "
            f"Score gap: {score_gap:.3f}, uncertainty: {uncertainty:.3f}"
        )
        
        return ConflictResolution(
            winning_claim=winner,
            confidence=winner_score,
            reasoning=reasoning,
            supporting_sources=supporting,
            opposing_sources=opposing,
            uncertainty=uncertainty
        )


class SourceRegistry:
    """Registry for managing sources."""
    
    def __init__(self):
        self.sources: Dict[str, Source] = {}
        self.claims: Dict[str, Claim] = {}
        self.trust_calculator = TrustCalculator()
        self.trust_propagator = TrustPropagator()
        self.conflict_resolver = ConflictResolver(self.trust_calculator)
    
    def register_source(self, source: Source):
        """Register a source."""
        self.sources[source.source_id] = source
    
    def get_source(self, source_id: str) -> Optional[Source]:
        """Get a source by ID."""
        return self.sources.get(source_id)
    
    def add_claim(self, claim: Claim):
        """Add a claim from a source."""
        self.claims[claim.claim_id] = claim
    
    def record_verification(
        self,
        source_id: str,
        correct: bool
    ):
        """Record a verification outcome for a source."""
        source = self.sources.get(source_id)
        if source:
            if correct:
                source.correct_count += 1
            else:
                source.incorrect_count += 1
    
    def add_citation(
        self,
        citing_id: str,
        cited_id: str
    ):
        """Record a citation between sources."""
        citing = self.sources.get(citing_id)
        cited = self.sources.get(cited_id)
        
        if citing:
            citing.cited_sources.add(cited_id)
        if cited:
            cited.cited_by.add(citing_id)
            cited.total_citations += 1
    
    def compute_trust_scores(self) -> Dict[str, TrustScore]:
        """Compute trust scores for all sources."""
        # First propagate trust
        propagated = self.trust_propagator.propagate(self.sources)
        
        # Update base trust with propagated values
        for sid, trust in propagated.items():
            if sid in self.sources:
                self.sources[sid].base_trust = trust
        
        # Compute final scores
        scores = {}
        for sid, source in self.sources.items():
            scores[sid] = self.trust_calculator.compute_trust(source)
        
        return scores
    
    def resolve_conflict(
        self,
        claim_ids: List[str]
    ) -> ConflictResolution:
        """Resolve conflict between claims."""
        claims = [
            self.claims[cid] for cid in claim_ids
            if cid in self.claims
        ]
        return self.conflict_resolver.resolve(claims, self.sources)
    
    def get_source_ranking(self) -> List[Tuple[str, float]]:
        """Get sources ranked by trust."""
        scores = self.compute_trust_scores()
        ranking = [
            (sid, score.total_score)
            for sid, score in scores.items()
        ]
        return sorted(ranking, key=lambda x: x[1], reverse=True)


class TemporalConsistencyChecker:
    """Checks temporal consistency of claims."""
    
    def check_consistency(
        self,
        claims: List[Claim]
    ) -> Dict[str, Any]:
        """Check for temporal inconsistencies."""
        if len(claims) < 2:
            return {"consistent": True, "issues": []}
        
        # Sort by timestamp
        sorted_claims = sorted(claims, key=lambda c: c.timestamp)
        
        issues = []
        
        # Check for claims that contradict earlier verified claims
        verified = [c for c in sorted_claims if c.verified is True]
        unverified = [c for c in sorted_claims if c.verified is not True]
        
        for unv in unverified:
            for ver in verified:
                if ver.timestamp < unv.timestamp:
                    # Check if unverified contradicts verified
                    if unv.claim_id in ver.contradicting_claims:
                        issues.append({
                            "type": "contradicts_verified",
                            "newer_claim": unv.claim_id,
                            "verified_claim": ver.claim_id,
                            "time_gap": (unv.timestamp - ver.timestamp).days
                        })
        
        return {
            "consistent": len(issues) == 0,
            "issues": issues,
            "claim_count": len(claims),
            "verified_count": len(verified)
        }


# Factory functions
def create_source(
    source_id: str,
    name: str,
    category: str = "unknown",
    base_trust: float = 0.5
) -> Source:
    """Create a source."""
    return Source(
        source_id=source_id,
        name=name,
        category=SourceCategory(category),
        base_trust=base_trust
    )


def create_claim(
    claim_id: str,
    content: str,
    source_id: str,
    timestamp: Optional[datetime] = None
) -> Claim:
    """Create a claim."""
    return Claim(
        claim_id=claim_id,
        content=content,
        source_id=source_id,
        timestamp=timestamp or datetime.now()
    )


def create_registry() -> SourceRegistry:
    """Create a source registry."""
    return SourceRegistry()
