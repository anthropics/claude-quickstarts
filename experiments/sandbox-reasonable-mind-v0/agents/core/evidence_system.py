"""
Evidence and Source Trust System - Phase 2 Enhancement

Implements:
- Citation requirements and validation
- Source trust weighting
- Confidence propagation through reasoning chains
- Hallucination guards with citation thresholds
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math
import re


class SourceType(Enum):
    """Types of evidence sources."""
    FACT = "fact"
    TOOL_RESULT = "tool_result"
    MEMORY = "memory"
    INFERENCE = "inference"
    USER_INPUT = "user_input"
    EXTERNAL_API = "external_api"
    LLM_GENERATION = "llm_generation"
    UNKNOWN = "unknown"


class TrustLevel(Enum):
    """Trust levels for sources."""
    HIGH = 0.95
    MEDIUM = 0.75
    LOW = 0.5
    UNTRUSTED = 0.25
    SPECULATIVE = 0.1


@dataclass
class SourceProfile:
    """Profile for a source with trust metrics."""
    source_id: str
    source_type: SourceType
    trust_level: TrustLevel = TrustLevel.MEDIUM
    custom_trust: Optional[float] = None
    recency_weight: float = 1.0  # Decay for old sources
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def trust_score(self) -> float:
        """Compute trust score from level or custom."""
        base = self.custom_trust if self.custom_trust else self.trust_level.value
        
        # Adjust based on track record
        if self.success_count + self.failure_count > 0:
            success_rate = self.success_count / (self.success_count + self.failure_count)
            base = 0.7 * base + 0.3 * success_rate
        
        return base * self.recency_weight


@dataclass
class EvidenceItem:
    """A piece of evidence with source and confidence."""
    evidence_id: str
    content: str
    source: SourceProfile
    confidence: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    reasoning_depth: int = 0  # How many inference steps from source
    parent_evidence: Optional[str] = None  # For derived evidence
    tags: Set[str] = field(default_factory=set)
    
    @property
    def effective_confidence(self) -> float:
        """Confidence adjusted by source trust and reasoning depth."""
        depth_decay = 0.95 ** self.reasoning_depth  # 5% decay per step
        return self.confidence * self.source.trust_score * depth_decay


@dataclass
class CitationRequirement:
    """Requirements for citations in a context."""
    min_citations: int = 1
    min_confidence: float = 0.5
    min_source_trust: float = 0.5
    max_reasoning_depth: int = 5
    require_multiple_sources: bool = False
    allow_llm_only: bool = False
    required_source_types: List[SourceType] = field(default_factory=list)


@dataclass
class EvidenceValidation:
    """Result of validating evidence for a claim."""
    is_valid: bool
    confidence: float
    citations: List[EvidenceItem]
    missing_requirements: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    speculative_content: List[str] = field(default_factory=list)


class SourceTrustRegistry:
    """
    Registry for source trust profiles.
    
    Maintains trust scores for different sources and updates
    them based on outcomes.
    """
    
    def __init__(self):
        self.sources: Dict[str, SourceProfile] = {}
        self._init_default_sources()
    
    def _init_default_sources(self) -> None:
        """Initialize default source profiles."""
        defaults = [
            SourceProfile(
                source_id="knowledge_base",
                source_type=SourceType.FACT,
                trust_level=TrustLevel.HIGH
            ),
            SourceProfile(
                source_id="tool_execution",
                source_type=SourceType.TOOL_RESULT,
                trust_level=TrustLevel.HIGH
            ),
            SourceProfile(
                source_id="memory_system",
                source_type=SourceType.MEMORY,
                trust_level=TrustLevel.MEDIUM
            ),
            SourceProfile(
                source_id="inference_engine",
                source_type=SourceType.INFERENCE,
                trust_level=TrustLevel.MEDIUM
            ),
            SourceProfile(
                source_id="user",
                source_type=SourceType.USER_INPUT,
                trust_level=TrustLevel.HIGH
            ),
            SourceProfile(
                source_id="llm_base",
                source_type=SourceType.LLM_GENERATION,
                trust_level=TrustLevel.LOW
            ),
        ]
        
        for source in defaults:
            self.sources[source.source_id] = source
    
    def get_source(self, source_id: str) -> Optional[SourceProfile]:
        """Get a source profile."""
        return self.sources.get(source_id)
    
    def register_source(self, profile: SourceProfile) -> None:
        """Register a new source."""
        self.sources[profile.source_id] = profile
    
    def update_trust(
        self,
        source_id: str,
        success: bool,
        learning_rate: float = 0.1
    ) -> None:
        """Update source trust based on outcome."""
        source = self.sources.get(source_id)
        if not source:
            return
        
        if success:
            source.success_count += 1
        else:
            source.failure_count += 1
        
        source.last_used = datetime.now().isoformat()
    
    def apply_recency_decay(
        self,
        max_age_days: int = 30,
        decay_rate: float = 0.01
    ) -> None:
        """Apply recency decay to all sources."""
        now = datetime.now()
        
        for source in self.sources.values():
            if source.last_used:
                try:
                    last_used = datetime.fromisoformat(source.last_used)
                    age_days = (now - last_used).days
                    if age_days > max_age_days:
                        decay = 1 - (decay_rate * (age_days - max_age_days))
                        source.recency_weight = max(0.5, decay)
                except (ValueError, TypeError):
                    pass


class ConfidenceChain:
    """
    Tracks confidence through a chain of reasoning.
    
    Implements confidence propagation with decay.
    """
    
    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self.base_confidence: float = 1.0
    
    def add_step(
        self,
        step_type: str,
        description: str,
        confidence: float,
        evidence: Optional[List[EvidenceItem]] = None
    ) -> float:
        """Add a reasoning step and compute resulting confidence."""
        step = {
            "step_type": step_type,
            "description": description,
            "input_confidence": self.current_confidence,
            "step_confidence": confidence,
            "evidence": evidence or [],
            "timestamp": datetime.now().isoformat()
        }
        
        # Propagate confidence using log-odds
        self.steps.append(step)
        
        return self.current_confidence
    
    @property
    def current_confidence(self) -> float:
        """Compute current confidence using log-odds propagation."""
        if not self.steps:
            return self.base_confidence
        
        # Use log-odds for proper probability combination
        log_odds_sum = 0.0
        for step in self.steps:
            conf = max(0.01, min(0.99, step["step_confidence"]))
            log_odds = math.log(conf / (1 - conf))
            log_odds_sum += log_odds
        
        # Convert back from log-odds
        combined = 1 / (1 + math.exp(-log_odds_sum / len(self.steps)))
        return combined
    
    def get_weakest_link(self) -> Optional[Dict[str, Any]]:
        """Get the step with lowest confidence."""
        if not self.steps:
            return None
        return min(self.steps, key=lambda s: s["step_confidence"])
    
    def get_rationale(self) -> str:
        """Generate rationale for current confidence level."""
        if not self.steps:
            return "No reasoning steps taken."
        
        rationale_parts = []
        for i, step in enumerate(self.steps, 1):
            rationale_parts.append(
                f"Step {i} ({step['step_type']}): {step['description']} "
                f"[confidence: {step['step_confidence']:.2f}]"
            )
        
        rationale_parts.append(f"Final confidence: {self.current_confidence:.2f}")
        
        weakest = self.get_weakest_link()
        if weakest and weakest["step_confidence"] < 0.5:
            rationale_parts.append(
                f"⚠️ Low confidence at: {weakest['description']}"
            )
        
        return "\n".join(rationale_parts)


class HallucinationGuard:
    """
    Guards against hallucination by requiring citations.
    
    Features:
    - Citation thresholds per claim type
    - Penalization for uncited spans
    - Speculative content labeling
    """
    
    def __init__(
        self,
        citation_threshold: float = 0.6,
        uncited_penalty: float = 0.3,
        require_citations_for_facts: bool = True,
        label_speculative: bool = True
    ):
        self.citation_threshold = citation_threshold
        self.uncited_penalty = uncited_penalty
        self.require_citations_for_facts = require_citations_for_facts
        self.label_speculative = label_speculative
        
        # Patterns that should require citations
        self.fact_patterns = [
            r"\b(is|are|was|were)\b.*\b(always|never|all|every|none)\b",
            r"\b(according to|research shows|studies indicate|data shows)\b",
            r"\b\d+(\.\d+)?%\b",  # Percentages
            r"\b(definitely|certainly|proven|confirmed)\b",
        ]
    
    def check_claim(
        self,
        claim: str,
        evidence: List[EvidenceItem]
    ) -> EvidenceValidation:
        """Check if a claim is properly supported by evidence."""
        warnings = []
        speculative = []
        
        # Check if claim requires citation
        requires_citation = self._requires_citation(claim)
        
        if not evidence:
            if requires_citation:
                return EvidenceValidation(
                    is_valid=False,
                    confidence=0.0,
                    citations=[],
                    missing_requirements=["No evidence provided for factual claim"],
                    warnings=["Claim appears factual but has no citations"]
                )
            else:
                # Non-factual claim, lower confidence but allowed
                return EvidenceValidation(
                    is_valid=True,
                    confidence=0.5 - self.uncited_penalty,
                    citations=[],
                    warnings=["No citations provided"],
                    speculative_content=[claim] if self.label_speculative else []
                )
        
        # Compute aggregate confidence from evidence
        total_confidence = 0.0
        valid_evidence = []
        
        for item in evidence:
            eff_conf = item.effective_confidence
            if eff_conf >= self.citation_threshold:
                valid_evidence.append(item)
                total_confidence += eff_conf
            else:
                warnings.append(
                    f"Evidence '{item.content[:50]}...' below threshold "
                    f"({eff_conf:.2f} < {self.citation_threshold:.2f})"
                )
        
        if not valid_evidence:
            return EvidenceValidation(
                is_valid=False,
                confidence=0.0,
                citations=evidence,
                missing_requirements=["No evidence meets confidence threshold"],
                warnings=warnings
            )
        
        # Normalize confidence
        avg_confidence = total_confidence / len(valid_evidence)
        
        # Check for LLM-only sources
        llm_only = all(
            e.source.source_type == SourceType.LLM_GENERATION
            for e in valid_evidence
        )
        
        if llm_only:
            avg_confidence *= 0.7
            warnings.append("All evidence from LLM generation only")
            if self.label_speculative:
                speculative.append(claim)
        
        return EvidenceValidation(
            is_valid=True,
            confidence=avg_confidence,
            citations=valid_evidence,
            warnings=warnings,
            speculative_content=speculative
        )
    
    def _requires_citation(self, claim: str) -> bool:
        """Check if claim requires citation."""
        if not self.require_citations_for_facts:
            return False
        
        for pattern in self.fact_patterns:
            if re.search(pattern, claim, re.IGNORECASE):
                return True
        
        return False
    
    def annotate_output(
        self,
        output: str,
        citations: Dict[str, List[EvidenceItem]]
    ) -> str:
        """Annotate output with citation markers and speculative labels."""
        annotated = output
        
        # Find uncited spans and mark them
        for sentence in re.split(r'[.!?]', output):
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if sentence is cited
            has_citation = any(
                sentence in cited_text or cited_text in sentence
                for cited_text in citations.keys()
            )
            
            if not has_citation and self._requires_citation(sentence):
                # Mark as speculative
                if self.label_speculative:
                    annotated = annotated.replace(
                        sentence,
                        f"[SPECULATIVE: {sentence}]"
                    )
        
        return annotated


class EvidenceValidator:
    """
    Validates evidence against citation requirements.
    """
    
    def __init__(
        self,
        trust_registry: Optional[SourceTrustRegistry] = None,
        hallucination_guard: Optional[HallucinationGuard] = None
    ):
        self.trust_registry = trust_registry or SourceTrustRegistry()
        self.hallucination_guard = hallucination_guard or HallucinationGuard()
    
    def validate(
        self,
        claim: str,
        evidence: List[EvidenceItem],
        requirements: Optional[CitationRequirement] = None
    ) -> EvidenceValidation:
        """Validate evidence for a claim."""
        requirements = requirements or CitationRequirement()
        missing = []
        warnings = []
        
        # Check minimum citations
        if len(evidence) < requirements.min_citations:
            missing.append(
                f"Need at least {requirements.min_citations} citations, "
                f"have {len(evidence)}"
            )
        
        # Check required source types
        if requirements.required_source_types:
            present_types = {e.source.source_type for e in evidence}
            for req_type in requirements.required_source_types:
                if req_type not in present_types:
                    missing.append(f"Missing required source type: {req_type.value}")
        
        # Check for multiple sources if required
        if requirements.require_multiple_sources:
            unique_sources = {e.source.source_id for e in evidence}
            if len(unique_sources) < 2:
                warnings.append("Multiple sources recommended but only one found")
        
        # Check LLM-only restriction
        if not requirements.allow_llm_only:
            if all(e.source.source_type == SourceType.LLM_GENERATION for e in evidence):
                missing.append("Cannot use LLM-only evidence for this claim")
        
        # Filter evidence by requirements
        valid_evidence = []
        for e in evidence:
            if e.effective_confidence < requirements.min_confidence:
                warnings.append(
                    f"Evidence '{e.content[:30]}...' below confidence threshold"
                )
                continue
            if e.source.trust_score < requirements.min_source_trust:
                warnings.append(
                    f"Evidence source '{e.source.source_id}' below trust threshold"
                )
                continue
            if e.reasoning_depth > requirements.max_reasoning_depth:
                warnings.append(
                    f"Evidence '{e.content[:30]}...' too many inference steps"
                )
                continue
            valid_evidence.append(e)
        
        # Run hallucination guard
        guard_result = self.hallucination_guard.check_claim(claim, valid_evidence)
        
        # Combine results
        is_valid = len(missing) == 0 and guard_result.is_valid
        
        return EvidenceValidation(
            is_valid=is_valid,
            confidence=guard_result.confidence,
            citations=valid_evidence,
            missing_requirements=missing + guard_result.missing_requirements,
            warnings=warnings + guard_result.warnings,
            speculative_content=guard_result.speculative_content
        )
    
    def create_evidence(
        self,
        content: str,
        source_id: str,
        confidence: float,
        reasoning_depth: int = 0,
        parent_evidence: Optional[str] = None
    ) -> EvidenceItem:
        """Create an evidence item with proper source profile."""
        source = self.trust_registry.get_source(source_id)
        if not source:
            # Create unknown source
            source = SourceProfile(
                source_id=source_id,
                source_type=SourceType.UNKNOWN,
                trust_level=TrustLevel.LOW
            )
            self.trust_registry.register_source(source)
        
        import hashlib
        evidence_id = hashlib.sha256(
            f"{content}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        return EvidenceItem(
            evidence_id=evidence_id,
            content=content,
            source=source,
            confidence=confidence,
            reasoning_depth=reasoning_depth,
            parent_evidence=parent_evidence
        )


class ConflictResolver:
    """
    Resolves conflicts between contradictory evidence.
    
    Uses trust + confidence + recency to determine which evidence to prefer.
    """
    
    def __init__(self, trust_registry: SourceTrustRegistry):
        self.trust_registry = trust_registry
    
    def resolve(
        self,
        evidence_a: EvidenceItem,
        evidence_b: EvidenceItem
    ) -> Tuple[EvidenceItem, str]:
        """
        Resolve conflict between two evidence items.
        
        Returns:
            (preferred_evidence, reason)
        """
        score_a = self._compute_resolution_score(evidence_a)
        score_b = self._compute_resolution_score(evidence_b)
        
        if score_a > score_b:
            reason = self._generate_reason(evidence_a, evidence_b, score_a, score_b)
            return evidence_a, reason
        elif score_b > score_a:
            reason = self._generate_reason(evidence_b, evidence_a, score_b, score_a)
            return evidence_b, reason
        else:
            # Tie: prefer more recent
            return evidence_a, "Equally scored, preferring first"
    
    def _compute_resolution_score(self, evidence: EvidenceItem) -> float:
        """Compute resolution score for evidence."""
        base = evidence.effective_confidence
        
        # Boost for higher-trust sources
        if evidence.source.trust_level == TrustLevel.HIGH:
            base *= 1.2
        
        # Penalty for deep inference chains
        if evidence.reasoning_depth > 3:
            base *= 0.8
        
        return base
    
    def _generate_reason(
        self,
        preferred: EvidenceItem,
        rejected: EvidenceItem,
        pref_score: float,
        rej_score: float
    ) -> str:
        """Generate explanation for preference."""
        reasons = []
        
        if preferred.source.trust_score > rejected.source.trust_score:
            reasons.append(f"higher source trust ({preferred.source.source_id})")
        
        if preferred.confidence > rejected.confidence:
            reasons.append(f"higher confidence ({preferred.confidence:.2f})")
        
        if preferred.reasoning_depth < rejected.reasoning_depth:
            reasons.append("fewer inference steps")
        
        if not reasons:
            reasons.append(f"higher overall score ({pref_score:.2f} vs {rej_score:.2f})")
        
        return f"Preferred due to: {', '.join(reasons)}"
