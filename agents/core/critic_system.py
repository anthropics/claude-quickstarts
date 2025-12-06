"""
Self-Checking and Debate System - Phase 2

Implements:
- Second-pass critic for reasoning validation
- Self-consistency checking
- Multi-agent debate for controversial claims
- Confidence calibration based on critique
"""

from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import random


class CritiqueType(Enum):
    """Types of critiques."""
    LOGICAL = "logical"  # Logic/validity issues
    FACTUAL = "factual"  # Factual accuracy
    COHERENCE = "coherence"  # Internal consistency
    COMPLETENESS = "completeness"  # Missing considerations
    BIAS = "bias"  # Potential biases
    ASSUMPTION = "assumption"  # Unstated assumptions


class CritiqueSeverity(Enum):
    """Severity of critique."""
    CRITICAL = "critical"  # Must be addressed
    MAJOR = "major"  # Should be addressed
    MINOR = "minor"  # Nice to address
    SUGGESTION = "suggestion"  # Optional improvement


class DebateOutcome(Enum):
    """Outcome of a debate."""
    CONSENSUS = "consensus"  # Agents agreed
    MAJORITY = "majority"  # Majority agreed
    SPLIT = "split"  # No agreement
    ESCALATE = "escalate"  # Needs human input


@dataclass
class Critique:
    """A single critique of reasoning."""
    critique_type: CritiqueType
    severity: CritiqueSeverity
    description: str
    target: str  # What is being critiqued
    suggestion: Optional[str] = None
    confidence: float = 0.8
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.critique_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "target": self.target,
            "suggestion": self.suggestion,
            "confidence": self.confidence
        }


@dataclass
class CritiqueResult:
    """Result of a critic pass."""
    critiques: List[Critique]
    overall_assessment: str
    revised_confidence: float
    should_revise: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def has_critical(self) -> bool:
        return any(c.severity == CritiqueSeverity.CRITICAL for c in self.critiques)
    
    @property
    def has_major(self) -> bool:
        return any(c.severity == CritiqueSeverity.MAJOR for c in self.critiques)


@dataclass
class DebatePosition:
    """A position in a debate."""
    agent_id: str
    claim: str
    arguments: List[str]
    confidence: float
    evidence: List[str] = field(default_factory=list)


@dataclass
class DebateRound:
    """A single round of debate."""
    round_number: int
    positions: List[DebatePosition]
    rebuttals: List[Dict[str, str]]  # agent_id -> rebuttal
    
    
@dataclass
class DebateResult:
    """Result of a multi-agent debate."""
    topic: str
    rounds: List[DebateRound]
    outcome: DebateOutcome
    winning_position: Optional[str]
    consensus_confidence: float
    key_agreements: List[str]
    key_disagreements: List[str]


class Critic(ABC):
    """Abstract base class for critics."""
    
    @abstractmethod
    def critique(
        self,
        reasoning: str,
        conclusion: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Critique]:
        """Generate critiques of reasoning."""
        ...


class LogicCritic(Critic):
    """Critic focused on logical validity."""
    
    # Common logical fallacy patterns
    FALLACY_PATTERNS = [
        ("affirming the consequent", r"if .+ then .+; .+ therefore .+"),
        ("denying the antecedent", r"if .+ then .+; not .+ therefore not .+"),
        ("hasty generalization", r"(all|every|always|never).+based on.+(one|few|single)"),
        ("false dichotomy", r"(either|only two).+(or|options)"),
        ("circular reasoning", r"because.+therefore.+because"),
        ("ad hominem", r"(person|character|motives).+(wrong|can't trust)"),
        ("appeal to authority", r"(expert|authority|famous).+says.+must be"),
        ("straw man", r"(actually|really) (saying|claiming|arguing).+not"),
    ]
    
    def critique(
        self,
        reasoning: str,
        conclusion: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Critique]:
        critiques = []
        reasoning_lower = reasoning.lower()
        
        # Check for fallacy patterns
        for fallacy_name, pattern in self.FALLACY_PATTERNS:
            import re
            if re.search(pattern, reasoning_lower):
                critiques.append(Critique(
                    critique_type=CritiqueType.LOGICAL,
                    severity=CritiqueSeverity.MAJOR,
                    description=f"Possible {fallacy_name} fallacy detected",
                    target=reasoning[:100],
                    suggestion=f"Review argument structure to avoid {fallacy_name}"
                ))
        
        # Check for unsupported leaps
        if "therefore" in reasoning_lower or "thus" in reasoning_lower:
            # Look for conclusion without proper premises
            sentences = reasoning.split(".")
            for i, sentence in enumerate(sentences):
                if "therefore" in sentence.lower() or "thus" in sentence.lower():
                    if i < 2:  # Very quick conclusion
                        critiques.append(Critique(
                            critique_type=CritiqueType.LOGICAL,
                            severity=CritiqueSeverity.MINOR,
                            description="Conclusion reached with minimal premises",
                            target=sentence.strip(),
                            suggestion="Consider adding more supporting premises"
                        ))
        
        # Check for contradictions
        if self._has_contradiction(reasoning):
            critiques.append(Critique(
                critique_type=CritiqueType.COHERENCE,
                severity=CritiqueSeverity.CRITICAL,
                description="Potential contradiction detected in reasoning",
                target=reasoning[:200],
                suggestion="Review for internal consistency"
            ))
        
        return critiques
    
    def _has_contradiction(self, text: str) -> bool:
        """Simple contradiction detection."""
        text_lower = text.lower()
        
        # Check for explicit contradictions
        contradiction_markers = [
            ("is true", "is false"),
            ("is valid", "is invalid"),
            ("all are", "not all are"),
            ("none are", "some are"),
            ("always", "never"),
            ("must be", "cannot be"),
        ]
        
        for positive, negative in contradiction_markers:
            if positive in text_lower and negative in text_lower:
                return True
        
        return False


class CompletenessСritic(Critic):
    """Critic focused on completeness of analysis."""
    
    def critique(
        self,
        reasoning: str,
        conclusion: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Critique]:
        critiques = []
        
        # Check for missing considerations
        if "however" not in reasoning.lower() and "but" not in reasoning.lower():
            critiques.append(Critique(
                critique_type=CritiqueType.COMPLETENESS,
                severity=CritiqueSeverity.MINOR,
                description="No counter-considerations mentioned",
                target="overall reasoning",
                suggestion="Consider addressing potential objections"
            ))
        
        # Check for unstated assumptions
        assumption_markers = ["obviously", "clearly", "of course", "naturally", "everyone knows"]
        for marker in assumption_markers:
            if marker in reasoning.lower():
                critiques.append(Critique(
                    critique_type=CritiqueType.ASSUMPTION,
                    severity=CritiqueSeverity.MINOR,
                    description=f"Possible unstated assumption ('{marker}')",
                    target=marker,
                    suggestion="Consider making implicit assumptions explicit"
                ))
        
        # Check for missing edge cases
        if context and context.get("domain") == "logic":
            edge_case_terms = ["except", "unless", "edge case", "boundary", "limit"]
            if not any(term in reasoning.lower() for term in edge_case_terms):
                critiques.append(Critique(
                    critique_type=CritiqueType.COMPLETENESS,
                    severity=CritiqueSeverity.SUGGESTION,
                    description="Edge cases not explicitly addressed",
                    target="analysis scope",
                    suggestion="Consider boundary conditions and exceptions"
                ))
        
        return critiques


class BiasCritic(Critic):
    """Critic focused on detecting potential biases."""
    
    BIAS_MARKERS = {
        "confirmation": ["proves that", "confirms", "as expected", "just as I thought"],
        "anchoring": ["initially", "first impression", "at first glance"],
        "availability": ["common", "typical", "usually", "in my experience"],
        "recency": ["recently", "latest", "just now", "current trend"],
    }
    
    def critique(
        self,
        reasoning: str,
        conclusion: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Critique]:
        critiques = []
        reasoning_lower = reasoning.lower()
        
        for bias_type, markers in self.BIAS_MARKERS.items():
            for marker in markers:
                if marker in reasoning_lower:
                    critiques.append(Critique(
                        critique_type=CritiqueType.BIAS,
                        severity=CritiqueSeverity.SUGGESTION,
                        description=f"Possible {bias_type} bias indicator: '{marker}'",
                        target=marker,
                        suggestion=f"Consider if {bias_type} bias is influencing the analysis"
                    ))
                    break  # One critique per bias type
        
        return critiques


class CriticSystem:
    """
    Orchestrates multiple critics for comprehensive review.
    """
    
    def __init__(self):
        self.critics: List[Critic] = [
            LogicCritic(),
            CompletenessСritic(),
            BiasCritic(),
        ]
        
        self.critique_history: List[CritiqueResult] = []
        self.revision_count = 0
    
    def add_critic(self, critic: Critic) -> None:
        """Add a custom critic."""
        self.critics.append(critic)
    
    def review(
        self,
        reasoning: str,
        conclusion: str,
        original_confidence: float = 0.8,
        context: Optional[Dict[str, Any]] = None
    ) -> CritiqueResult:
        """Run all critics and aggregate results."""
        all_critiques = []
        
        for critic in self.critics:
            critiques = critic.critique(reasoning, conclusion, context)
            all_critiques.extend(critiques)
        
        # Calculate revised confidence
        revised_confidence = self._calculate_revised_confidence(
            original_confidence, 
            all_critiques
        )
        
        # Determine if revision needed
        should_revise = any(
            c.severity in (CritiqueSeverity.CRITICAL, CritiqueSeverity.MAJOR)
            for c in all_critiques
        )
        
        # Generate assessment
        assessment = self._generate_assessment(all_critiques)
        
        result = CritiqueResult(
            critiques=all_critiques,
            overall_assessment=assessment,
            revised_confidence=revised_confidence,
            should_revise=should_revise
        )
        
        self.critique_history.append(result)
        return result
    
    def self_consistency_check(
        self,
        responses: List[str],
        threshold: float = 0.7
    ) -> Tuple[bool, float, str]:
        """
        Check if multiple reasoning attempts reach consistent conclusions.
        
        Returns:
            (is_consistent, agreement_score, summary)
        """
        if len(responses) < 2:
            return True, 1.0, "Single response - consistency not applicable"
        
        # Extract conclusions (last sentence of each response)
        conclusions = []
        for resp in responses:
            sentences = [s.strip().lower() for s in resp.strip().split(".") if s.strip()]
            if sentences:
                conclusions.append(sentences[-1])
        
        # Calculate pairwise similarity
        total_pairs = 0
        similar_pairs = 0
        
        for i in range(len(conclusions)):
            for j in range(i + 1, len(conclusions)):
                total_pairs += 1
                if self._are_similar(conclusions[i], conclusions[j]):
                    similar_pairs += 1
        
        agreement_score = similar_pairs / total_pairs if total_pairs > 0 else 1.0
        is_consistent = agreement_score >= threshold
        
        summary = (
            f"Agreement score: {agreement_score:.2f}. "
            f"{similar_pairs}/{total_pairs} conclusion pairs agree. "
            f"{'Consistent' if is_consistent else 'Inconsistent'}."
        )
        
        return is_consistent, agreement_score, summary
    
    def _are_similar(self, text1: str, text2: str) -> bool:
        """Check if two texts express similar conclusions."""
        # Simple word overlap check
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return False
        
        overlap = len(words1 & words2)
        union = len(words1 | words2)
        
        return (overlap / union) > 0.5 if union > 0 else False
    
    def _calculate_revised_confidence(
        self,
        original: float,
        critiques: List[Critique]
    ) -> float:
        """Calculate revised confidence based on critiques."""
        penalty = 0.0
        
        for critique in critiques:
            if critique.severity == CritiqueSeverity.CRITICAL:
                penalty += 0.3
            elif critique.severity == CritiqueSeverity.MAJOR:
                penalty += 0.15
            elif critique.severity == CritiqueSeverity.MINOR:
                penalty += 0.05
            # SUGGESTION doesn't affect confidence
        
        # Apply penalty with floor
        revised = max(0.1, original - penalty)
        return round(revised, 2)
    
    def _generate_assessment(self, critiques: List[Critique]) -> str:
        """Generate overall assessment from critiques."""
        if not critiques:
            return "No significant issues found. Reasoning appears sound."
        
        critical = sum(1 for c in critiques if c.severity == CritiqueSeverity.CRITICAL)
        major = sum(1 for c in critiques if c.severity == CritiqueSeverity.MAJOR)
        minor = sum(1 for c in critiques if c.severity == CritiqueSeverity.MINOR)
        
        if critical > 0:
            return f"Critical issues found ({critical}). Reasoning requires significant revision."
        elif major > 0:
            return f"Major issues found ({major}). Reasoning should be strengthened."
        elif minor > 0:
            return f"Minor issues found ({minor}). Reasoning is acceptable with improvements."
        else:
            return "Only suggestions found. Reasoning is sound."


class DebateAgent:
    """An agent that can participate in debates."""
    
    def __init__(
        self,
        agent_id: str,
        reasoning_fn: Optional[Callable[[str], str]] = None,
        bias: Optional[str] = None  # For devil's advocate
    ):
        self.agent_id = agent_id
        self.reasoning_fn = reasoning_fn or self._default_reasoning
        self.bias = bias
        self.positions_taken: List[DebatePosition] = []
    
    def take_position(
        self,
        topic: str,
        context: Optional[Dict[str, Any]] = None
    ) -> DebatePosition:
        """Take a position on a topic."""
        # Generate reasoning
        reasoning = self.reasoning_fn(topic)
        
        # Apply bias if devil's advocate
        if self.bias == "contrary":
            reasoning = f"However, consider the opposite: {reasoning}"
        
        # Extract arguments
        arguments = [s.strip() for s in reasoning.split(".") if s.strip()][:5]
        
        # Calculate confidence
        confidence = 0.7 + random.uniform(-0.2, 0.2)
        
        position = DebatePosition(
            agent_id=self.agent_id,
            claim=arguments[0] if arguments else topic,
            arguments=arguments,
            confidence=confidence
        )
        
        self.positions_taken.append(position)
        return position
    
    def rebut(
        self,
        opposing_position: DebatePosition
    ) -> str:
        """Generate a rebuttal to an opposing position."""
        rebuttals = [
            f"While {opposing_position.claim}, we must consider...",
            f"The argument that {opposing_position.arguments[0] if opposing_position.arguments else 'this'} overlooks...",
            "This reasoning has merit but fails to account for...",
            "The evidence cited does not fully support the claim because...",
        ]
        return random.choice(rebuttals)
    
    def _default_reasoning(self, topic: str) -> str:
        """Default reasoning when no custom function provided."""
        return f"Considering {topic}, the key factors are relevance, validity, and completeness."


class DebateSystem:
    """
    Orchestrates multi-agent debates.
    """
    
    def __init__(self, max_rounds: int = 3):
        self.max_rounds = max_rounds
        self.agents: List[DebateAgent] = []
        self.debate_history: List[DebateResult] = []
    
    def add_agent(self, agent: DebateAgent) -> None:
        """Add an agent to the debate."""
        self.agents.append(agent)
    
    def create_default_agents(self) -> None:
        """Create a default set of debate agents."""
        self.agents = [
            DebateAgent("advocate", bias=None),
            DebateAgent("critic", bias="contrary"),
            DebateAgent("synthesizer", bias=None),
        ]
    
    def debate(
        self,
        topic: str,
        context: Optional[Dict[str, Any]] = None
    ) -> DebateResult:
        """Run a multi-agent debate on a topic."""
        if len(self.agents) < 2:
            self.create_default_agents()
        
        rounds: List[DebateRound] = []
        
        # Initial positions
        positions = [
            agent.take_position(topic, context)
            for agent in self.agents
        ]
        
        for round_num in range(self.max_rounds):
            rebuttals = {}
            
            # Each agent rebuts others
            for i, agent in enumerate(self.agents):
                for j, other_position in enumerate(positions):
                    if i != j:
                        rebuttal = agent.rebut(other_position)
                        rebuttals[agent.agent_id] = rebuttal
                        break  # One rebuttal per agent per round
            
            # Convert rebuttals dict to list format
            rebuttals_list = [{"agent_id": k, "rebuttal": v} for k, v in rebuttals.items()]
            
            rounds.append(DebateRound(
                round_number=round_num + 1,
                positions=positions.copy(),
                rebuttals=rebuttals_list
            ))
            
            # Update positions based on debate (simplified)
            for i, agent in enumerate(self.agents):
                # Positions may shift slightly
                if positions[i].confidence > 0.3:
                    positions[i].confidence -= 0.1 * random.random()
        
        # Determine outcome
        outcome, winning, agreements, disagreements = self._determine_outcome(positions)
        
        result = DebateResult(
            topic=topic,
            rounds=rounds,
            outcome=outcome,
            winning_position=winning,
            consensus_confidence=sum(p.confidence for p in positions) / len(positions),
            key_agreements=agreements,
            key_disagreements=disagreements
        )
        
        self.debate_history.append(result)
        return result
    
    def _determine_outcome(
        self,
        positions: List[DebatePosition]
    ) -> Tuple[DebateOutcome, Optional[str], List[str], List[str]]:
        """Determine the outcome of a debate."""
        if not positions:
            return DebateOutcome.SPLIT, None, [], []
        
        # Find highest confidence position
        sorted_positions = sorted(positions, key=lambda p: p.confidence, reverse=True)
        top_position = sorted_positions[0]
        
        # Check for consensus (all high confidence in similar direction)
        high_confidence = [p for p in positions if p.confidence > 0.7]
        
        if len(high_confidence) == len(positions):
            return (
                DebateOutcome.CONSENSUS,
                top_position.claim,
                [top_position.claim],
                []
            )
        elif len(high_confidence) > len(positions) / 2:
            return (
                DebateOutcome.MAJORITY,
                top_position.claim,
                [top_position.claim],
                [p.claim for p in positions if p.confidence <= 0.5]
            )
        else:
            return (
                DebateOutcome.SPLIT,
                None,
                [],
                [p.claim for p in positions]
            )
    
    def should_escalate(self, result: DebateResult) -> bool:
        """Determine if debate result should be escalated to human."""
        return (
            result.outcome == DebateOutcome.SPLIT or
            result.consensus_confidence < 0.5
        )


class SelfChecker:
    """
    Combines critic and debate systems for comprehensive self-checking.
    """
    
    def __init__(self):
        self.critic_system = CriticSystem()
        self.debate_system = DebateSystem()
        
    def full_review(
        self,
        reasoning: str,
        conclusion: str,
        confidence: float = 0.8,
        run_debate: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run a full self-checking review.
        
        Returns comprehensive review including:
        - Critic analysis
        - Self-consistency (if multiple samples)
        - Debate results (if enabled)
        - Final recommendation
        """
        # Run critic system
        critique_result = self.critic_system.review(
            reasoning, conclusion, confidence, context
        )
        
        result = {
            "critique": {
                "critiques": [c.to_dict() for c in critique_result.critiques],
                "assessment": critique_result.overall_assessment,
                "revised_confidence": critique_result.revised_confidence,
                "should_revise": critique_result.should_revise
            },
            "original_confidence": confidence,
            "final_confidence": critique_result.revised_confidence
        }
        
        # Run debate if requested and there are major issues
        if run_debate and critique_result.has_major:
            debate_result = self.debate_system.debate(conclusion, context)
            result["debate"] = {
                "outcome": debate_result.outcome.value,
                "winning_position": debate_result.winning_position,
                "consensus_confidence": debate_result.consensus_confidence,
                "should_escalate": self.debate_system.should_escalate(debate_result)
            }
            
            # Adjust confidence based on debate
            if debate_result.outcome == DebateOutcome.CONSENSUS:
                result["final_confidence"] = min(0.95, result["final_confidence"] + 0.1)
            elif debate_result.outcome == DebateOutcome.SPLIT:
                result["final_confidence"] = max(0.3, result["final_confidence"] - 0.2)
        
        # Generate recommendation
        result["recommendation"] = self._generate_recommendation(result)
        
        return result
    
    def _generate_recommendation(self, result: Dict[str, Any]) -> str:
        """Generate a recommendation based on review results."""
        final_conf = result["final_confidence"]
        should_revise = result["critique"]["should_revise"]
        
        if final_conf >= 0.8 and not should_revise:
            return "ACCEPT: Reasoning is sound and confident."
        elif final_conf >= 0.6 and not should_revise:
            return "ACCEPT_WITH_CAVEAT: Reasoning is acceptable but note limitations."
        elif final_conf >= 0.4:
            return "REVISE: Address critiques before accepting conclusion."
        else:
            return "REJECT: Significant issues require major revision or escalation."
