"""
Hallucination Mitigation System - Advanced Enhancement

Provides hallucination detection and prevention:
- Proof-or-flag pattern for claims
- Citation validation
- Factual consistency checking
- Confidence calibration for uncertain outputs
"""

from typing import List, Dict, Any, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import re
import hashlib


class ClaimStatus(Enum):
    """Status of a claim verification."""
    VERIFIED = "verified"  # Proven with evidence
    SUPPORTED = "supported"  # Evidence exists but not conclusive
    UNCERTAIN = "uncertain"  # Cannot determine
    UNSUPPORTED = "unsupported"  # No evidence found
    CONTRADICTED = "contradicted"  # Evidence contradicts
    FLAGGED = "flagged"  # Flagged for review


class EvidenceType(Enum):
    """Types of evidence."""
    CITATION = "citation"  # From cited source
    RETRIEVED = "retrieved"  # From retrieval
    COMPUTED = "computed"  # Computed/verified
    SELF_CONSISTENT = "self_consistent"  # Multiple generations agree
    EXTERNAL = "external"  # External fact check


@dataclass
class Claim:
    """A claim that needs verification."""
    claim_id: str
    text: str
    source: str
    confidence: float = 0.5
    category: str = "factual"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    """Evidence for or against a claim."""
    evidence_id: str
    evidence_type: EvidenceType
    content: str
    source: str
    relevance: float
    supports: bool  # True if supports, False if contradicts
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class VerificationResult:
    """Result of claim verification."""
    claim: Claim
    status: ClaimStatus
    confidence: float
    evidence: List[Evidence]
    explanation: str
    flagged: bool
    suggested_revision: Optional[str] = None


@dataclass
class FactualityScore:
    """Factuality score for a text."""
    score: float  # 0-1, higher is more factual
    verified_claims: int
    unverified_claims: int
    flagged_claims: int
    details: Dict[str, Any] = field(default_factory=dict)


class ClaimExtractor:
    """Extracts verifiable claims from text."""
    
    def __init__(self):
        # Patterns for identifying factual claims
        self.factual_patterns = [
            r'\b(is|are|was|were)\b.*\b(the|a|an)\b',
            r'\b(has|have|had)\b.*\b(been|the)\b',
            r'\b(first|largest|smallest|oldest|newest)\b',
            r'\b(in \d{4})\b',
            r'\b(\d+%|\d+ percent)\b',
            r'\b(according to|studies show|research indicates)\b',
        ]
    
    def extract(self, text: str) -> List[Claim]:
        """Extract claims from text."""
        claims = []
        sentences = self._split_sentences(text)
        
        for idx, sentence in enumerate(sentences):
            if self._is_factual_claim(sentence):
                claim = Claim(
                    claim_id=f"claim_{idx}_{hashlib.md5(sentence.encode()).hexdigest()[:8]}",
                    text=sentence.strip(),
                    source="generated",
                    confidence=self._estimate_confidence(sentence),
                    category=self._categorize_claim(sentence)
                )
                claims.append(claim)
        
        return claims
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s.strip()]
    
    def _is_factual_claim(self, sentence: str) -> bool:
        """Determine if sentence contains factual claim."""
        sentence_lower = sentence.lower()
        
        # Check for factual patterns
        for pattern in self.factual_patterns:
            if re.search(pattern, sentence_lower):
                return True
        
        # Check for specific indicators
        factual_words = ['is', 'was', 'were', 'has', 'have', 'had', 'will']
        return any(f' {word} ' in f' {sentence_lower} ' for word in factual_words)
    
    def _estimate_confidence(self, sentence: str) -> float:
        """Estimate confidence based on language."""
        hedging_words = [
            'may', 'might', 'could', 'possibly', 'perhaps',
            'likely', 'probably', 'seems', 'appears', 'suggests'
        ]
        
        sentence_lower = sentence.lower()
        hedge_count = sum(1 for w in hedging_words if w in sentence_lower)
        
        # More hedging = lower confidence
        return max(0.3, 1.0 - 0.15 * hedge_count)
    
    def _categorize_claim(self, sentence: str) -> str:
        """Categorize the type of claim."""
        sentence_lower = sentence.lower()
        
        if any(w in sentence_lower for w in ['study', 'research', 'survey']):
            return "scientific"
        if re.search(r'\d{4}', sentence):
            return "historical"
        if re.search(r'\d+%|\d+ percent', sentence):
            return "statistical"
        if any(w in sentence_lower for w in ['law', 'regulation', 'court']):
            return "legal"
        return "factual"


class EvidenceGatherer(ABC):
    """Abstract base for evidence gathering."""
    
    @abstractmethod
    def gather(self, claim: Claim) -> List[Evidence]:
        """Gather evidence for a claim."""


class RetrievalEvidenceGatherer(EvidenceGatherer):
    """Gathers evidence from retrieval system."""
    
    def __init__(
        self,
        retrieval_fn: Optional[Callable[[str], List[Dict[str, Any]]]] = None
    ):
        self.retrieval_fn = retrieval_fn
    
    def gather(self, claim: Claim) -> List[Evidence]:
        """Gather evidence from retrieval."""
        if not self.retrieval_fn:
            return []
        
        results = self.retrieval_fn(claim.text)
        evidence = []
        
        for idx, result in enumerate(results[:5]):
            content = result.get("content", "")
            source = result.get("source", "unknown")
            score = result.get("score", 0.5)
            
            # Determine if evidence supports or contradicts
            supports = self._check_support(claim.text, content)
            
            evidence.append(Evidence(
                evidence_id=f"ret_{idx}",
                evidence_type=EvidenceType.RETRIEVED,
                content=content[:500],
                source=source,
                relevance=score,
                supports=supports,
                confidence=score * 0.8
            ))
        
        return evidence
    
    def _check_support(self, claim: str, evidence: str) -> bool:
        """Check if evidence supports claim."""
        # Simplified: check term overlap
        claim_terms = set(claim.lower().split())
        evidence_terms = set(evidence.lower().split())
        
        overlap = len(claim_terms & evidence_terms)
        return overlap / max(len(claim_terms), 1) > 0.3


class CitationEvidenceGatherer(EvidenceGatherer):
    """Gathers evidence from citations."""
    
    def __init__(self, citation_db: Optional[Dict[str, str]] = None):
        self.citation_db = citation_db or {}
    
    def gather(self, claim: Claim) -> List[Evidence]:
        """Gather evidence from citations in claim."""
        evidence = []
        
        # Find citation patterns
        citation_patterns = [
            r'\(([^)]+, \d{4})\)',  # (Author, Year)
            r'\[(\d+)\]',  # [1], [2], etc.
            r'according to ([^,]+)',
        ]
        
        for pattern in citation_patterns:
            matches = re.findall(pattern, claim.text, re.IGNORECASE)
            for match in matches:
                if match in self.citation_db:
                    evidence.append(Evidence(
                        evidence_id=f"cite_{match}",
                        evidence_type=EvidenceType.CITATION,
                        content=self.citation_db[match],
                        source=match,
                        relevance=0.9,
                        supports=True,
                        confidence=0.85
                    ))
        
        return evidence


class SelfConsistencyChecker:
    """Checks self-consistency across multiple generations."""
    
    def __init__(self, num_samples: int = 5):
        self.num_samples = num_samples
    
    def check(
        self,
        claim: Claim,
        alternative_claims: List[str]
    ) -> Evidence:
        """Check if claim is consistent with alternatives."""
        if not alternative_claims:
            return Evidence(
                evidence_id="self_check",
                evidence_type=EvidenceType.SELF_CONSISTENT,
                content="No alternative claims to compare",
                source="self_consistency",
                relevance=0.5,
                supports=True,
                confidence=0.5
            )
        
        # Check agreement
        claim_lower = claim.text.lower()
        agreements = sum(
            1 for alt in alternative_claims
            if self._semantic_similarity(claim_lower, alt.lower()) > 0.7
        )
        
        agreement_rate = agreements / len(alternative_claims)
        
        return Evidence(
            evidence_id="self_check",
            evidence_type=EvidenceType.SELF_CONSISTENT,
            content=f"{agreements}/{len(alternative_claims)} alternatives agree",
            source="self_consistency",
            relevance=0.8,
            supports=agreement_rate > 0.5,
            confidence=agreement_rate
        )
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity (simplified)."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        overlap = len(words1 & words2)
        return 2 * overlap / (len(words1) + len(words2))


class ClaimVerifier:
    """Verifies claims using multiple evidence sources."""
    
    def __init__(
        self,
        gatherers: Optional[List[EvidenceGatherer]] = None,
        verification_threshold: float = 0.7,
        flag_threshold: float = 0.3
    ):
        self.gatherers = gatherers or []
        self.verification_threshold = verification_threshold
        self.flag_threshold = flag_threshold
    
    def add_gatherer(self, gatherer: EvidenceGatherer):
        """Add an evidence gatherer."""
        self.gatherers.append(gatherer)
    
    def verify(self, claim: Claim) -> VerificationResult:
        """Verify a claim."""
        all_evidence: List[Evidence] = []
        
        # Gather evidence from all sources
        for gatherer in self.gatherers:
            evidence = gatherer.gather(claim)
            all_evidence.extend(evidence)
        
        # Aggregate evidence
        if not all_evidence:
            return VerificationResult(
                claim=claim,
                status=ClaimStatus.UNCERTAIN,
                confidence=0.5,
                evidence=[],
                explanation="No evidence found",
                flagged=True
            )
        
        # Compute support score
        supporting = [e for e in all_evidence if e.supports]
        contradicting = [e for e in all_evidence if not e.supports]
        
        support_score = sum(e.confidence * e.relevance for e in supporting)
        contradict_score = sum(e.confidence * e.relevance for e in contradicting)
        
        total_weight = support_score + contradict_score
        if total_weight > 0:
            net_support = (support_score - contradict_score) / total_weight
        else:
            net_support = 0.0
        
        # Normalize to [0, 1]
        normalized = (net_support + 1) / 2
        
        # Determine status
        if normalized >= self.verification_threshold:
            status = ClaimStatus.VERIFIED if normalized > 0.85 else ClaimStatus.SUPPORTED
        elif normalized <= self.flag_threshold:
            status = ClaimStatus.CONTRADICTED if contradicting else ClaimStatus.UNSUPPORTED
        else:
            status = ClaimStatus.UNCERTAIN
        
        flagged = status in [ClaimStatus.UNCERTAIN, ClaimStatus.UNSUPPORTED, ClaimStatus.CONTRADICTED]
        
        explanation = self._generate_explanation(
            claim, supporting, contradicting, normalized, status
        )
        
        return VerificationResult(
            claim=claim,
            status=status,
            confidence=normalized,
            evidence=all_evidence,
            explanation=explanation,
            flagged=flagged,
            suggested_revision=self._suggest_revision(claim, status, all_evidence) if flagged else None
        )
    
    def _generate_explanation(
        self,
        claim: Claim,
        supporting: List[Evidence],
        contradicting: List[Evidence],
        score: float,
        status: ClaimStatus
    ) -> str:
        """Generate explanation for verification result."""
        parts = [f"Status: {status.value} (confidence: {score:.2f})"]
        
        if supporting:
            parts.append(f"Supporting evidence: {len(supporting)}")
        if contradicting:
            parts.append(f"Contradicting evidence: {len(contradicting)}")
        
        return " | ".join(parts)
    
    def _suggest_revision(
        self,
        claim: Claim,
        status: ClaimStatus,
        evidence: List[Evidence]
    ) -> str:
        """Suggest revision for flagged claim."""
        if status == ClaimStatus.CONTRADICTED:
            contradicting = [e for e in evidence if not e.supports]
            if contradicting:
                return f"Consider revising based on: {contradicting[0].content[:100]}..."
        
        if status == ClaimStatus.UNSUPPORTED:
            return f"Add citation or evidence for: '{claim.text[:50]}...'"
        
        if status == ClaimStatus.UNCERTAIN:
            return f"Consider hedging: 'It appears that' or 'Evidence suggests that'"
        
        return ""


class HallucinationDetector:
    """Main hallucination detection system."""
    
    def __init__(
        self,
        verifier: Optional[ClaimVerifier] = None,
        extractor: Optional[ClaimExtractor] = None
    ):
        self.extractor = extractor or ClaimExtractor()
        self.verifier = verifier or ClaimVerifier()
        self.consistency_checker = SelfConsistencyChecker()
    
    def analyze(
        self,
        text: str,
        alternatives: Optional[List[str]] = None
    ) -> Tuple[FactualityScore, List[VerificationResult]]:
        """Analyze text for potential hallucinations."""
        # Extract claims
        claims = self.extractor.extract(text)
        
        if not claims:
            return FactualityScore(
                score=1.0,
                verified_claims=0,
                unverified_claims=0,
                flagged_claims=0
            ), []
        
        # Verify each claim
        results = []
        for claim in claims:
            result = self.verifier.verify(claim)
            
            # Add self-consistency check if alternatives provided
            if alternatives:
                consistency = self.consistency_checker.check(claim, alternatives)
                result.evidence.append(consistency)
            
            results.append(result)
        
        # Compute factuality score
        verified = sum(1 for r in results if r.status == ClaimStatus.VERIFIED)
        supported = sum(1 for r in results if r.status == ClaimStatus.SUPPORTED)
        flagged = sum(1 for r in results if r.flagged)
        
        score = (verified + 0.7 * supported) / max(len(results), 1)
        
        return FactualityScore(
            score=score,
            verified_claims=verified,
            unverified_claims=len(results) - verified - supported,
            flagged_claims=flagged,
            details={
                "total_claims": len(claims),
                "supported_claims": supported
            }
        ), results
    
    def proof_or_flag(
        self,
        text: str,
        require_proof_threshold: float = 0.5
    ) -> Tuple[str, List[str]]:
        """Apply proof-or-flag pattern to text."""
        score, results = self.analyze(text)
        
        flagged_texts = []
        annotated_parts = []
        
        # Get original sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        claim_texts = {r.claim.text for r in results if r.flagged}
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if this sentence was flagged
            is_flagged = any(
                self._text_matches(sentence, ct) for ct in claim_texts
            )
            
            if is_flagged:
                flagged_texts.append(sentence)
                annotated_parts.append(f"[UNVERIFIED: {sentence}]")
            else:
                annotated_parts.append(sentence)
        
        return ' '.join(annotated_parts), flagged_texts
    
    def _text_matches(self, text1: str, text2: str) -> bool:
        """Check if texts match (fuzzy)."""
        # Normalize
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()
        
        # Exact or substring match
        return t1 == t2 or t1 in t2 or t2 in t1


class ConfidenceCalibrator:
    """Calibrates confidence scores for outputs."""
    
    def __init__(self, temperature: float = 1.0):
        self.temperature = temperature
        self.calibration_data: List[Tuple[float, bool]] = []
    
    def calibrate(self, confidence: float) -> float:
        """Apply temperature scaling to confidence."""
        import math
        
        # Convert to logit
        if confidence <= 0:
            confidence = 0.01
        if confidence >= 1:
            confidence = 0.99
        
        logit = math.log(confidence / (1 - confidence))
        
        # Apply temperature
        scaled_logit = logit / self.temperature
        
        # Convert back to probability
        return 1 / (1 + math.exp(-scaled_logit))
    
    def record_outcome(self, confidence: float, was_correct: bool):
        """Record outcome for calibration learning."""
        self.calibration_data.append((confidence, was_correct))
    
    def compute_calibration_error(self) -> float:
        """Compute Expected Calibration Error."""
        if not self.calibration_data:
            return 0.0
        
        # Bin by confidence
        bins: Dict[int, List[Tuple[float, bool]]] = {}
        for conf, correct in self.calibration_data:
            bin_idx = int(conf * 10)
            if bin_idx not in bins:
                bins[bin_idx] = []
            bins[bin_idx].append((conf, correct))
        
        ece = 0.0
        total = len(self.calibration_data)
        
        for items in bins.values():
            if not items:
                continue
            
            avg_conf = sum(c for c, _ in items) / len(items)
            accuracy = sum(1 for _, correct in items if correct) / len(items)
            
            ece += len(items) / total * abs(avg_conf - accuracy)
        
        return ece


# Factory functions
def create_hallucination_detector(
    retrieval_fn: Optional[Callable[[str], List[Dict[str, Any]]]] = None
) -> HallucinationDetector:
    """Create a hallucination detector."""
    verifier = ClaimVerifier()
    
    if retrieval_fn:
        verifier.add_gatherer(RetrievalEvidenceGatherer(retrieval_fn))
    
    verifier.add_gatherer(CitationEvidenceGatherer())
    
    return HallucinationDetector(verifier=verifier)


def create_claim_verifier() -> ClaimVerifier:
    """Create a claim verifier."""
    return ClaimVerifier()
