"""
Self-Consistency and Voting System - Advanced Enhancement

Provides multi-sample self-consistency:
- Generate N reasoning chains
- Vote/rerank with majority or logit-based scoring
- Hallucination reduction through consensus
- Chain-of-Verification (CoVe) patterns
"""

from typing import List, Dict, Any, Optional, Tuple, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import math
import hashlib
import statistics


class VotingMethod(Enum):
    """Methods for aggregating votes."""
    MAJORITY = "majority"  # Simple majority vote
    WEIGHTED = "weighted"  # Confidence-weighted voting
    LOGIT = "logit"  # Logit-based aggregation
    BORDA = "borda"  # Borda count ranking
    CONSENSUS = "consensus"  # Require threshold agreement


class ConsistencyLevel(Enum):
    """Levels of consistency across samples."""
    UNANIMOUS = "unanimous"  # All agree
    STRONG = "strong"  # >80% agree
    MODERATE = "moderate"  # >60% agree
    WEAK = "weak"  # >40% agree
    INCONSISTENT = "inconsistent"  # No clear winner


@dataclass
class ReasoningChain:
    """A single reasoning chain/sample."""
    chain_id: str
    steps: List[str]
    conclusion: str
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    generation_time_ms: float = 0.0
    
    def fingerprint(self) -> str:
        """Generate fingerprint for deduplication."""
        content = f"{self.conclusion}::{':'.join(self.steps)}"
        return hashlib.md5(content.encode()).hexdigest()[:16]


@dataclass
class Vote:
    """A vote from a reasoning chain."""
    chain_id: str
    answer: str
    confidence: float
    reasoning_steps: int
    normalized_answer: str = ""
    
    def __post_init__(self):
        if not self.normalized_answer:
            # Normalize answer for comparison
            self.normalized_answer = self.answer.strip().lower()


@dataclass
class ConsistencyResult:
    """Result of self-consistency aggregation."""
    winner: str
    vote_count: int
    total_votes: int
    consistency_level: ConsistencyLevel
    agreement_ratio: float
    confidence: float
    alternative_answers: List[Tuple[str, int]]
    voting_method: VotingMethod
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Result of chain-of-verification."""
    original_claim: str
    verified: bool
    verification_confidence: float
    evidence_found: List[str]
    contradictions: List[str]
    speculative: bool
    revision: Optional[str] = None


class AnswerNormalizer:
    """Normalizes answers for comparison."""
    
    def __init__(self, case_sensitive: bool = False):
        self.case_sensitive = case_sensitive
        self._equivalences: Dict[str, str] = {}
    
    def add_equivalence(self, canonical: str, variants: List[str]) -> None:
        """Add equivalent forms of an answer."""
        for variant in variants:
            key = variant if self.case_sensitive else variant.lower()
            self._equivalences[key] = canonical
    
    def normalize(self, answer: str) -> str:
        """Normalize an answer to canonical form."""
        answer = answer.strip()
        key = answer if self.case_sensitive else answer.lower()
        
        # Check explicit equivalences
        if key in self._equivalences:
            return self._equivalences[key]
        
        # Basic normalization
        normalized = key
        
        # Remove common prefixes
        prefixes = ["the answer is", "answer:", "result:", "therefore"]
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        
        # Remove punctuation at end
        while normalized and normalized[-1] in ".,!?;:":
            normalized = normalized[:-1]
        
        return normalized


class SelfConsistencyVoter:
    """
    Aggregates multiple reasoning chains through voting.
    
    Implements various voting schemes for self-consistency.
    """
    
    def __init__(
        self,
        method: VotingMethod = VotingMethod.WEIGHTED,
        consensus_threshold: float = 0.6,
        normalizer: Optional[AnswerNormalizer] = None
    ):
        self.method = method
        self.consensus_threshold = consensus_threshold
        self.normalizer = normalizer or AnswerNormalizer()
    
    def aggregate(
        self,
        chains: List[ReasoningChain]
    ) -> ConsistencyResult:
        """Aggregate reasoning chains through voting."""
        if not chains:
            return ConsistencyResult(
                winner="",
                vote_count=0,
                total_votes=0,
                consistency_level=ConsistencyLevel.INCONSISTENT,
                agreement_ratio=0.0,
                confidence=0.0,
                alternative_answers=[],
                voting_method=self.method
            )
        
        # Convert chains to votes
        votes = [
            Vote(
                chain_id=chain.chain_id,
                answer=chain.conclusion,
                confidence=chain.confidence,
                reasoning_steps=len(chain.steps)
            )
            for chain in chains
        ]
        
        # Normalize and count
        answer_votes: Dict[str, List[Vote]] = {}
        for vote in votes:
            normalized = self.normalizer.normalize(vote.answer)
            vote.normalized_answer = normalized
            if normalized not in answer_votes:
                answer_votes[normalized] = []
            answer_votes[normalized].append(vote)
        
        # Apply voting method
        if self.method == VotingMethod.MAJORITY:
            return self._majority_vote(answer_votes, len(votes))
        elif self.method == VotingMethod.WEIGHTED:
            return self._weighted_vote(answer_votes, len(votes))
        elif self.method == VotingMethod.LOGIT:
            return self._logit_vote(answer_votes, len(votes))
        elif self.method == VotingMethod.BORDA:
            return self._borda_count(chains)
        elif self.method == VotingMethod.CONSENSUS:
            return self._consensus_vote(answer_votes, len(votes))
        else:
            return self._majority_vote(answer_votes, len(votes))
    
    def _majority_vote(
        self,
        answer_votes: Dict[str, List[Vote]],
        total: int
    ) -> ConsistencyResult:
        """Simple majority voting."""
        sorted_answers = sorted(
            answer_votes.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        winner, winner_votes = sorted_answers[0]
        vote_count = len(winner_votes)
        agreement = vote_count / total
        
        return ConsistencyResult(
            winner=winner,
            vote_count=vote_count,
            total_votes=total,
            consistency_level=self._get_consistency_level(agreement),
            agreement_ratio=agreement,
            confidence=agreement,
            alternative_answers=[
                (ans, len(votes))
                for ans, votes in sorted_answers[1:4]
            ],
            voting_method=VotingMethod.MAJORITY
        )
    
    def _weighted_vote(
        self,
        answer_votes: Dict[str, List[Vote]],
        total: int
    ) -> ConsistencyResult:
        """Confidence-weighted voting."""
        weighted_scores: Dict[str, float] = {}
        
        for answer, votes in answer_votes.items():
            # Sum of confidences
            weighted_scores[answer] = sum(v.confidence for v in votes)
        
        total_weight = sum(weighted_scores.values())
        
        sorted_answers = sorted(
            weighted_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        winner, winner_score = sorted_answers[0]
        vote_count = len(answer_votes[winner])
        agreement = winner_score / total_weight if total_weight > 0 else 0
        
        return ConsistencyResult(
            winner=winner,
            vote_count=vote_count,
            total_votes=total,
            consistency_level=self._get_consistency_level(agreement),
            agreement_ratio=vote_count / total,
            confidence=agreement,
            alternative_answers=[
                (ans, len(answer_votes[ans]))
                for ans, _ in sorted_answers[1:4]
                if ans in answer_votes
            ],
            voting_method=VotingMethod.WEIGHTED,
            details={"weighted_scores": weighted_scores}
        )
    
    def _logit_vote(
        self,
        answer_votes: Dict[str, List[Vote]],
        total: int
    ) -> ConsistencyResult:
        """Logit-based voting (log-odds aggregation)."""
        logit_scores: Dict[str, float] = {}
        
        for answer, votes in answer_votes.items():
            # Sum of log-odds
            log_odds_sum = 0.0
            for vote in votes:
                p = max(0.01, min(0.99, vote.confidence))
                log_odds_sum += math.log(p / (1 - p))
            logit_scores[answer] = log_odds_sum
        
        # Convert back to probabilities via softmax
        max_logit = max(logit_scores.values())
        exp_scores = {
            ans: math.exp(score - max_logit)
            for ans, score in logit_scores.items()
        }
        total_exp = sum(exp_scores.values())
        probabilities = {
            ans: exp / total_exp
            for ans, exp in exp_scores.items()
        }
        
        sorted_answers = sorted(
            probabilities.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        winner, winner_prob = sorted_answers[0]
        vote_count = len(answer_votes[winner])
        
        return ConsistencyResult(
            winner=winner,
            vote_count=vote_count,
            total_votes=total,
            consistency_level=self._get_consistency_level(winner_prob),
            agreement_ratio=vote_count / total,
            confidence=winner_prob,
            alternative_answers=[
                (ans, len(answer_votes[ans]))
                for ans, _ in sorted_answers[1:4]
                if ans in answer_votes
            ],
            voting_method=VotingMethod.LOGIT,
            details={"probabilities": probabilities}
        )
    
    def _borda_count(
        self,
        chains: List[ReasoningChain]
    ) -> ConsistencyResult:
        """Borda count ranking (rank-based voting)."""
        # Sort chains by confidence to get rankings
        sorted_chains = sorted(chains, key=lambda c: c.confidence, reverse=True)
        
        # Assign Borda points
        n = len(chains)
        borda_points: Dict[str, float] = {}
        answer_votes: Dict[str, List[Vote]] = {}
        
        for rank, chain in enumerate(sorted_chains):
            normalized = self.normalizer.normalize(chain.conclusion)
            points = n - rank
            borda_points[normalized] = borda_points.get(normalized, 0) + points
            
            if normalized not in answer_votes:
                answer_votes[normalized] = []
            answer_votes[normalized].append(Vote(
                chain_id=chain.chain_id,
                answer=chain.conclusion,
                confidence=chain.confidence,
                reasoning_steps=len(chain.steps)
            ))
        
        sorted_answers = sorted(
            borda_points.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        winner, winner_points = sorted_answers[0]
        vote_count = len(answer_votes[winner])
        max_points = n * len(answer_votes[winner])  # Maximum possible for this answer
        
        return ConsistencyResult(
            winner=winner,
            vote_count=vote_count,
            total_votes=n,
            consistency_level=self._get_consistency_level(vote_count / n),
            agreement_ratio=vote_count / n,
            confidence=winner_points / max_points if max_points > 0 else 0,
            alternative_answers=[
                (ans, len(answer_votes.get(ans, [])))
                for ans, _ in sorted_answers[1:4]
            ],
            voting_method=VotingMethod.BORDA,
            details={"borda_points": borda_points}
        )
    
    def _consensus_vote(
        self,
        answer_votes: Dict[str, List[Vote]],
        total: int
    ) -> ConsistencyResult:
        """Require threshold consensus."""
        sorted_answers = sorted(
            answer_votes.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        winner, winner_votes = sorted_answers[0]
        vote_count = len(winner_votes)
        agreement = vote_count / total
        
        # Check if consensus threshold is met
        if agreement < self.consensus_threshold:
            # No consensus - mark as uncertain
            return ConsistencyResult(
                winner=winner,
                vote_count=vote_count,
                total_votes=total,
                consistency_level=ConsistencyLevel.INCONSISTENT,
                agreement_ratio=agreement,
                confidence=0.0,  # Low confidence due to no consensus
                alternative_answers=[
                    (ans, len(votes))
                    for ans, votes in sorted_answers[1:4]
                ],
                voting_method=VotingMethod.CONSENSUS,
                details={"consensus_met": False}
            )
        
        return ConsistencyResult(
            winner=winner,
            vote_count=vote_count,
            total_votes=total,
            consistency_level=self._get_consistency_level(agreement),
            agreement_ratio=agreement,
            confidence=agreement,
            alternative_answers=[
                (ans, len(votes))
                for ans, votes in sorted_answers[1:4]
            ],
            voting_method=VotingMethod.CONSENSUS,
            details={"consensus_met": True}
        )
    
    def _get_consistency_level(self, agreement: float) -> ConsistencyLevel:
        """Map agreement ratio to consistency level."""
        if agreement >= 1.0:
            return ConsistencyLevel.UNANIMOUS
        elif agreement >= 0.8:
            return ConsistencyLevel.STRONG
        elif agreement >= 0.6:
            return ConsistencyLevel.MODERATE
        elif agreement >= 0.4:
            return ConsistencyLevel.WEAK
        else:
            return ConsistencyLevel.INCONSISTENT


class ChainOfVerification:
    """
    Chain-of-Verification (CoVe) pattern.
    
    After drafting an answer, runs verification checks.
    """
    
    def __init__(
        self,
        evidence_retriever: Optional[Callable[[str], List[str]]] = None,
        min_evidence: int = 1
    ):
        self.evidence_retriever = evidence_retriever
        self.min_evidence = min_evidence
    
    def verify(
        self,
        claim: str,
        context: Optional[Dict[str, Any]] = None
    ) -> VerificationResult:
        """
        Verify a claim against evidence.
        
        Returns verification result with confidence.
        """
        evidence: List[str] = []
        contradictions: List[str] = []
        
        # Retrieve evidence if retriever available
        if self.evidence_retriever:
            try:
                retrieved = self.evidence_retriever(claim)
                evidence.extend(retrieved)
            except Exception:
                pass
        
        # Check context for supporting evidence
        if context:
            for key, value in context.items():
                if isinstance(value, str):
                    if self._supports_claim(claim, value):
                        evidence.append(f"Context[{key}]: {value[:100]}...")
                    elif self._contradicts_claim(claim, value):
                        contradictions.append(f"Context[{key}]: {value[:100]}...")
        
        # Determine verification status
        has_evidence = len(evidence) >= self.min_evidence
        has_contradictions = len(contradictions) > 0
        
        if has_evidence and not has_contradictions:
            verified = True
            confidence = min(1.0, 0.5 + 0.1 * len(evidence))
        elif has_contradictions:
            verified = False
            confidence = max(0.0, 0.5 - 0.1 * len(contradictions))
        else:
            # No evidence - speculative
            verified = False
            confidence = 0.3
        
        speculative = not has_evidence and not has_contradictions
        
        return VerificationResult(
            original_claim=claim,
            verified=verified,
            verification_confidence=confidence,
            evidence_found=evidence,
            contradictions=contradictions,
            speculative=speculative,
            revision=None if verified else self._suggest_revision(claim, contradictions)
        )
    
    def _supports_claim(self, claim: str, evidence: str) -> bool:
        """Check if evidence supports claim (simplified)."""
        claim_words = set(claim.lower().split())
        evidence_words = set(evidence.lower().split())
        overlap = len(claim_words & evidence_words)
        return overlap >= 3
    
    def _contradicts_claim(self, claim: str, evidence: str) -> bool:
        """Check for contradiction indicators."""
        negation_words = {"not", "no", "never", "false", "incorrect", "wrong"}
        evidence_lower = evidence.lower()
        
        # Check if evidence contains claim + negation
        claim_words = set(claim.lower().split())
        evidence_words = set(evidence_lower.split())
        
        has_overlap = len(claim_words & evidence_words) >= 2
        has_negation = bool(negation_words & evidence_words)
        
        return has_overlap and has_negation
    
    def _suggest_revision(
        self,
        claim: str,
        contradictions: List[str]
    ) -> Optional[str]:
        """Suggest revision based on contradictions."""
        if not contradictions:
            return f"[NEEDS EVIDENCE] {claim}"
        return f"[CONTRADICTED] Original: {claim}"


@dataclass
class HallucinationCheck:
    """Result of hallucination check."""
    text: str
    span_start: int
    span_end: int
    is_speculative: bool
    confidence: float
    evidence_status: str  # "cited", "verified", "unverified", "speculative"
    label: str


class HallucinationDetector:
    """Detects potential hallucinations in generated text."""
    
    def __init__(self):
        self._speculative_markers = [
            "might", "could", "possibly", "perhaps", "maybe",
            "i think", "i believe", "it seems", "likely",
            "probably", "presumably"
        ]
        self._confidence_markers = [
            "definitely", "certainly", "clearly", "obviously",
            "without doubt", "absolutely"
        ]
    
    def check_text(
        self,
        text: str,
        cited_spans: Optional[List[Tuple[int, int]]] = None,
        verified_facts: Optional[List[str]] = None
    ) -> List[HallucinationCheck]:
        """
        Check text for potential hallucinations.
        
        Returns list of checks for each sentence/span.
        """
        results = []
        sentences = self._split_sentences(text)
        
        cited_spans = cited_spans or []
        verified_facts = verified_facts or []
        
        offset = 0
        for sentence in sentences:
            start = text.find(sentence, offset)
            end = start + len(sentence)
            offset = end
            
            # Check if span is cited
            is_cited = any(
                cs[0] <= start and cs[1] >= end
                for cs in cited_spans
            )
            
            # Check if matches verified fact
            is_verified = any(
                self._matches_fact(sentence, fact)
                for fact in verified_facts
            )
            
            # Check for speculative language
            is_speculative = any(
                marker in sentence.lower()
                for marker in self._speculative_markers
            )
            
            # Check for overconfident language
            is_overconfident = any(
                marker in sentence.lower()
                for marker in self._confidence_markers
            )
            
            # Determine status
            if is_cited:
                status = "cited"
                confidence = 0.9
            elif is_verified:
                status = "verified"
                confidence = 0.8
            elif is_speculative:
                status = "speculative"
                confidence = 0.4
            else:
                status = "unverified"
                confidence = 0.5
            
            # Generate label
            if status == "cited":
                label = "[CITED]"
            elif status == "verified":
                label = "[VERIFIED]"
            elif is_speculative:
                label = "[SPECULATIVE]"
            elif is_overconfident:
                label = "[NEEDS_VERIFICATION]"
            else:
                label = "[UNVERIFIED]"
            
            results.append(HallucinationCheck(
                text=sentence,
                span_start=start,
                span_end=end,
                is_speculative=is_speculative,
                confidence=confidence,
                evidence_status=status,
                label=label
            ))
        
        return results
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        import re
        sentences = re.split(r'[.!?]+\s*', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _matches_fact(self, sentence: str, fact: str) -> bool:
        """Check if sentence matches a verified fact."""
        sentence_words = set(sentence.lower().split())
        fact_words = set(fact.lower().split())
        overlap = len(sentence_words & fact_words)
        return overlap >= 3


@dataclass
class SelfConsistencyConfig:
    """Configuration for self-consistency sampling."""
    num_samples: int = 5
    voting_method: VotingMethod = VotingMethod.WEIGHTED
    consensus_threshold: float = 0.6
    temperature: float = 0.7
    enable_verification: bool = True
    max_latency_ms: float = 5000.0


class SelfConsistencyPipeline:
    """
    Complete self-consistency pipeline.
    
    Generates multiple samples, votes, verifies, and flags hallucinations.
    """
    
    def __init__(self, config: Optional[SelfConsistencyConfig] = None):
        self.config = config or SelfConsistencyConfig()
        self.voter = SelfConsistencyVoter(
            method=self.config.voting_method,
            consensus_threshold=self.config.consensus_threshold
        )
        self.verifier = ChainOfVerification()
        self.hallucination_detector = HallucinationDetector()
    
    def process(
        self,
        chains: List[ReasoningChain],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process multiple reasoning chains through full pipeline.
        
        Returns aggregated result with verification and hallucination checks.
        """
        # Step 1: Vote for best answer
        consistency_result = self.voter.aggregate(chains)
        
        # Step 2: Verify the winning answer
        verification = None
        if self.config.enable_verification:
            verification = self.verifier.verify(
                consistency_result.winner,
                context
            )
        
        # Step 3: Check for hallucinations in the answer
        hallucination_checks = self.hallucination_detector.check_text(
            consistency_result.winner
        )
        
        # Step 4: Compute overall quality score
        quality_score = self._compute_quality(
            consistency_result,
            verification,
            hallucination_checks
        )
        
        return {
            "answer": consistency_result.winner,
            "confidence": consistency_result.confidence,
            "consistency": consistency_result,
            "verification": verification,
            "hallucination_checks": hallucination_checks,
            "quality_score": quality_score,
            "needs_human_review": quality_score < 0.5
        }
    
    def _compute_quality(
        self,
        consistency: ConsistencyResult,
        verification: Optional[VerificationResult],
        hallucination_checks: List[HallucinationCheck]
    ) -> float:
        """Compute overall quality score."""
        score = consistency.confidence * 0.4
        
        if verification:
            score += verification.verification_confidence * 0.3
        else:
            score += 0.15  # Neutral without verification
        
        # Hallucination penalty
        if hallucination_checks:
            unverified_ratio = sum(
                1 for h in hallucination_checks
                if h.evidence_status in ("unverified", "speculative")
            ) / len(hallucination_checks)
            score += (1 - unverified_ratio) * 0.3
        else:
            score += 0.15
        
        return min(1.0, max(0.0, score))


# Convenience functions

def create_voting_aggregator(
    method: str = "weighted",
    threshold: float = 0.6
) -> SelfConsistencyVoter:
    """Create a voting aggregator."""
    voting_method = VotingMethod[method.upper()]
    return SelfConsistencyVoter(
        method=voting_method,
        consensus_threshold=threshold
    )


def aggregate_chains(
    chains: List[ReasoningChain],
    method: str = "weighted"
) -> ConsistencyResult:
    """Aggregate reasoning chains with specified voting method."""
    voter = create_voting_aggregator(method)
    return voter.aggregate(chains)


def verify_claim(
    claim: str,
    context: Optional[Dict[str, Any]] = None
) -> VerificationResult:
    """Verify a claim against context."""
    verifier = ChainOfVerification()
    return verifier.verify(claim, context)
