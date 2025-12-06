"""
Enhanced Debate System - Phase 2 Enhancement

Provides advanced adversarial verification and debate:
- Structured argument representation
- Adversarial attack generation
- Multi-perspective debate
- Confidence-weighted consensus
- Argument quality scoring
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ArgumentType(Enum):
    """Types of arguments in structured debate."""
    CLAIM = "claim"  # Main assertion
    PREMISE = "premise"  # Supporting premise
    EVIDENCE = "evidence"  # Factual evidence
    INFERENCE = "inference"  # Derived conclusion
    REBUTTAL = "rebuttal"  # Counter-argument
    CONCESSION = "concession"  # Acknowledged weakness
    QUALIFICATION = "qualification"  # Condition or limit


class AttackType(Enum):
    """Types of adversarial attacks on arguments."""
    COUNTEREXAMPLE = "counterexample"  # Specific case that refutes
    UNDERCUT = "undercut"  # Attacks the inference
    REBUT = "rebut"  # Attacks the conclusion
    PREMISE_ATTACK = "premise_attack"  # Challenges a premise
    ALTERNATIVE = "alternative"  # Proposes different conclusion


class ConsensusMethod(Enum):
    """Methods for reaching consensus."""
    UNANIMOUS = "unanimous"  # All must agree
    SUPERMAJORITY = "supermajority"  # 2/3 must agree
    MAJORITY = "majority"  # > 50% must agree
    WEIGHTED = "weighted"  # Weight by confidence
    BORDA = "borda"  # Borda count for rankings


@dataclass
class ArgumentNode:
    """A node in an argument structure."""
    node_id: str
    argument_type: ArgumentType
    content: str
    confidence: float
    supports: List[str] = field(default_factory=list)  # IDs of nodes this supports
    attacks: List[str] = field(default_factory=list)  # IDs of nodes this attacks
    source: Optional[str] = None  # Citation or agent ID
    quality_score: float = 0.5


@dataclass
class ArgumentStructure:
    """Complete structured argument."""
    structure_id: str
    main_claim: str
    nodes: Dict[str, ArgumentNode] = field(default_factory=dict)
    root_nodes: List[str] = field(default_factory=list)  # Top-level claims
    
    def add_node(self, node: ArgumentNode) -> None:
        """Add a node to the structure."""
        self.nodes[node.node_id] = node
        if node.argument_type == ArgumentType.CLAIM and not node.supports:
            self.root_nodes.append(node.node_id)
    
    def get_supporters(self, node_id: str) -> List[ArgumentNode]:
        """Get nodes that support a given node."""
        return [
            n for n in self.nodes.values()
            if node_id in n.supports
        ]
    
    def get_attackers(self, node_id: str) -> List[ArgumentNode]:
        """Get nodes that attack a given node."""
        return [
            n for n in self.nodes.values()
            if node_id in n.attacks
        ]


@dataclass
class AdversarialAttack:
    """An adversarial attack on an argument."""
    attack_id: str
    attack_type: AttackType
    target_node_id: str
    attack_content: str
    strength: float  # 0-1, how strong is this attack
    confidence: float
    generated_by: str  # Agent or method that generated it


@dataclass
class DebateAgent:
    """An agent participating in debate."""
    agent_id: str
    name: str
    perspective: str  # e.g., "skeptic", "advocate", "neutral"
    expertise_areas: List[str] = field(default_factory=list)
    confidence_bias: float = 0.0  # -0.2 to 0.2, tendency to over/under confidence
    
    
@dataclass
class DebateVote:
    """A vote from an agent on a position."""
    agent_id: str
    position_id: str
    confidence: float
    reasoning: str


@dataclass
class ConsensusResult:
    """Result of reaching consensus."""
    method: ConsensusMethod
    reached: bool
    winning_position: Optional[str]
    agreement_level: float  # 0-1
    votes: List[DebateVote]
    dissenting_views: List[str]


class ArgumentBuilder:
    """Builder for creating structured arguments."""
    
    def __init__(self, structure_id: str, main_claim: str):
        self.structure = ArgumentStructure(
            structure_id=structure_id,
            main_claim=main_claim
        )
        self._node_counter = 0
    
    def _next_id(self) -> str:
        self._node_counter += 1
        return f"node_{self._node_counter}"
    
    def add_claim(
        self, 
        content: str, 
        confidence: float = 0.8
    ) -> str:
        """Add a claim node."""
        node_id = self._next_id()
        node = ArgumentNode(
            node_id=node_id,
            argument_type=ArgumentType.CLAIM,
            content=content,
            confidence=confidence
        )
        self.structure.add_node(node)
        return node_id
    
    def add_premise(
        self, 
        content: str, 
        supports: str,
        confidence: float = 0.8
    ) -> str:
        """Add a premise supporting another node."""
        node_id = self._next_id()
        node = ArgumentNode(
            node_id=node_id,
            argument_type=ArgumentType.PREMISE,
            content=content,
            confidence=confidence,
            supports=[supports]
        )
        self.structure.add_node(node)
        return node_id
    
    def add_evidence(
        self, 
        content: str, 
        supports: str,
        source: Optional[str] = None,
        confidence: float = 0.9
    ) -> str:
        """Add evidence supporting another node."""
        node_id = self._next_id()
        node = ArgumentNode(
            node_id=node_id,
            argument_type=ArgumentType.EVIDENCE,
            content=content,
            confidence=confidence,
            supports=[supports],
            source=source
        )
        self.structure.add_node(node)
        return node_id
    
    def add_rebuttal(
        self, 
        content: str, 
        attacks: str,
        confidence: float = 0.7
    ) -> str:
        """Add a rebuttal attacking another node."""
        node_id = self._next_id()
        node = ArgumentNode(
            node_id=node_id,
            argument_type=ArgumentType.REBUTTAL,
            content=content,
            confidence=confidence,
            attacks=[attacks]
        )
        self.structure.add_node(node)
        return node_id
    
    def build(self) -> ArgumentStructure:
        """Build and return the argument structure."""
        return self.structure


class ArgumentQualityScorer:
    """Scores the quality of arguments."""
    
    def __init__(self):
        self._weights = {
            "support_count": 0.2,
            "evidence_quality": 0.25,
            "attack_resistance": 0.2,
            "internal_consistency": 0.2,
            "source_quality": 0.15
        }
    
    def score_node(
        self, 
        node: ArgumentNode, 
        structure: ArgumentStructure
    ) -> float:
        """Score a single argument node."""
        scores = {}
        
        # Support count - more support is better
        supporters = structure.get_supporters(node.node_id)
        scores["support_count"] = min(1.0, len(supporters) / 3)
        
        # Evidence quality
        evidence_nodes = [
            s for s in supporters 
            if s.argument_type == ArgumentType.EVIDENCE
        ]
        if evidence_nodes:
            scores["evidence_quality"] = sum(e.confidence for e in evidence_nodes) / len(evidence_nodes)
        else:
            scores["evidence_quality"] = 0.3  # Penalty for no evidence
        
        # Attack resistance
        attackers = structure.get_attackers(node.node_id)
        if attackers:
            avg_attack_strength = sum(a.confidence for a in attackers) / len(attackers)
            scores["attack_resistance"] = 1.0 - (avg_attack_strength * 0.5)
        else:
            scores["attack_resistance"] = 0.8  # No attacks yet
        
        # Internal consistency (placeholder)
        scores["internal_consistency"] = 0.8
        
        # Source quality
        if node.source:
            scores["source_quality"] = 0.9  # Has citation
        else:
            scores["source_quality"] = 0.5
        
        # Weighted average
        total = sum(
            self._weights[k] * scores[k] 
            for k in self._weights
        )
        
        return total
    
    def score_structure(self, structure: ArgumentStructure) -> Dict[str, float]:
        """Score an entire argument structure."""
        if not structure.nodes:
            return {"overall": 0.0}
        
        node_scores = {
            node_id: self.score_node(node, structure)
            for node_id, node in structure.nodes.items()
        }
        
        # Root nodes matter more
        root_avg = sum(
            node_scores.get(r, 0.5) 
            for r in structure.root_nodes
        ) / max(len(structure.root_nodes), 1)
        
        all_avg = sum(node_scores.values()) / len(node_scores)
        
        return {
            "overall": 0.6 * root_avg + 0.4 * all_avg,
            "root_quality": root_avg,
            "avg_node_quality": all_avg,
            "node_scores": node_scores
        }


class AdversarialGenerator:
    """Generates adversarial attacks on arguments."""
    
    def __init__(self):
        self._attack_templates = {
            AttackType.COUNTEREXAMPLE: [
                "Consider the case where {premise} but {conclusion} does not hold",
                "What about situations where {condition} is not true?",
                "This fails in the edge case of {edge_case}"
            ],
            AttackType.UNDERCUT: [
                "The inference from {premise} to {conclusion} is not valid because",
                "Even if {premise} is true, it doesn't follow that {conclusion}",
                "The reasoning assumes {assumption} which may not hold"
            ],
            AttackType.REBUT: [
                "The conclusion is incorrect because {counter_evidence}",
                "Evidence suggests the opposite: {contrary_evidence}",
                "This contradicts {known_fact}"
            ],
            AttackType.PREMISE_ATTACK: [
                "The premise '{premise}' is not well-supported",
                "There is reason to doubt that {premise}",
                "The claim '{premise}' requires verification"
            ],
            AttackType.ALTERNATIVE: [
                "An alternative explanation is {alternative}",
                "The same evidence supports {alternative_conclusion}",
                "Consider instead that {alternative}"
            ]
        }
    
    def generate_attacks(
        self,
        structure: ArgumentStructure,
        target_node_id: Optional[str] = None,
        attack_types: Optional[List[AttackType]] = None
    ) -> List[AdversarialAttack]:
        """Generate adversarial attacks on an argument structure."""
        attacks = []
        attack_types = attack_types or list(AttackType)
        
        # Determine which nodes to attack
        if target_node_id:
            target_nodes = [structure.nodes.get(target_node_id)]
        else:
            # Attack root nodes and high-confidence nodes
            target_nodes = [
                structure.nodes[nid] 
                for nid in structure.root_nodes
            ] + [
                n for n in structure.nodes.values()
                if n.confidence > 0.7
            ]
        
        for node in target_nodes:
            if node is None:
                continue
            
            for attack_type in attack_types:
                attack = self._generate_attack(node, attack_type, structure)
                if attack:
                    attacks.append(attack)
        
        return attacks
    
    def _generate_attack(
        self,
        node: ArgumentNode,
        attack_type: AttackType,
        structure: ArgumentStructure
    ) -> Optional[AdversarialAttack]:
        """Generate a single attack on a node."""
        templates = self._attack_templates.get(attack_type, [])
        if not templates:
            return None
        
        # Select template and fill in
        template = templates[0]  # Would randomly select in practice
        
        # Extract key elements from node
        content = node.content
        premise = content[:50] if len(content) > 50 else content
        
        attack_content = template.format(
            premise=premise,
            conclusion=structure.main_claim[:50],
            condition="the stated conditions",
            edge_case="extreme values",
            assumption="unstated assumptions",
            counter_evidence="contradicting data",
            contrary_evidence="opposing findings",
            known_fact="established knowledge",
            alternative="an alternative interpretation",
            alternative_conclusion="a different conclusion"
        )
        
        # Calculate attack strength based on node type and confidence
        base_strength = 0.5
        if node.argument_type == ArgumentType.CLAIM:
            base_strength = 0.6
        elif node.argument_type == ArgumentType.EVIDENCE:
            base_strength = 0.4  # Harder to attack evidence
        
        return AdversarialAttack(
            attack_id=f"attack_{node.node_id}_{attack_type.value}",
            attack_type=attack_type,
            target_node_id=node.node_id,
            attack_content=attack_content,
            strength=base_strength,
            confidence=0.7,
            generated_by="adversarial_generator"
        )


class MultiPerspectiveDebate:
    """Manages multi-perspective debate between agents."""
    
    def __init__(self):
        self.agents: List[DebateAgent] = []
        self._positions: Dict[str, ArgumentStructure] = {}
        self._votes: List[DebateVote] = []
    
    def add_agent(self, agent: DebateAgent) -> None:
        """Add an agent to the debate."""
        self.agents.append(agent)
    
    def add_standard_agents(self) -> None:
        """Add a standard set of debate agents."""
        standard_agents = [
            DebateAgent(
                agent_id="advocate",
                name="Devil's Advocate",
                perspective="skeptic",
                expertise_areas=["logic", "critical_thinking"]
            ),
            DebateAgent(
                agent_id="supporter",
                name="Steel Man",
                perspective="advocate",
                expertise_areas=["argument_strengthening"]
            ),
            DebateAgent(
                agent_id="neutral",
                name="Neutral Arbiter",
                perspective="neutral",
                expertise_areas=["evaluation", "synthesis"]
            ),
            DebateAgent(
                agent_id="fact_checker",
                name="Fact Checker",
                perspective="evidence_focused",
                expertise_areas=["verification", "sources"]
            )
        ]
        for agent in standard_agents:
            self.add_agent(agent)
    
    def submit_position(
        self, 
        agent_id: str, 
        position: ArgumentStructure
    ) -> None:
        """Submit a position from an agent."""
        self._positions[agent_id] = position
    
    def conduct_round(
        self,
        topic: str,
        positions: Dict[str, str]  # agent_id -> position text
    ) -> Dict[str, Any]:
        """Conduct a debate round."""
        round_results = {
            "topic": topic,
            "positions": positions,
            "critiques": {},
            "votes": []
        }
        
        # Each agent critiques others' positions
        for agent in self.agents:
            agent_critiques = []
            for other_id, position in positions.items():
                if other_id != agent.agent_id:
                    critique = self._generate_critique(agent, position)
                    agent_critiques.append({
                        "target": other_id,
                        "critique": critique
                    })
            round_results["critiques"][agent.agent_id] = agent_critiques
        
        # Each agent votes
        for agent in self.agents:
            vote = self._agent_vote(agent, positions)
            self._votes.append(vote)
            round_results["votes"].append(vote)
        
        return round_results
    
    def _generate_critique(
        self, 
        agent: DebateAgent, 
        position: str
    ) -> str:
        """Generate a critique from an agent's perspective."""
        if agent.perspective == "skeptic":
            return f"From a skeptical view: What evidence supports '{position[:50]}'?"
        elif agent.perspective == "advocate":
            return f"To strengthen: '{position[:50]}' could be supported by..."
        elif agent.perspective == "evidence_focused":
            return f"Verification needed: '{position[:50]}' requires source citation"
        else:
            return f"Evaluation: '{position[:50]}' appears reasonable but needs refinement"
    
    def _agent_vote(
        self, 
        agent: DebateAgent, 
        positions: Dict[str, str]
    ) -> DebateVote:
        """Agent votes for best position."""
        # Simple voting logic - would be more sophisticated in practice
        position_ids = list(positions.keys())
        if not position_ids:
            return DebateVote(
                agent_id=agent.agent_id,
                position_id="none",
                confidence=0.0,
                reasoning="No positions to vote on"
            )
        
        # Vote for first non-self position (placeholder)
        chosen = position_ids[0]
        for pid in position_ids:
            if pid != agent.agent_id:
                chosen = pid
                break
        
        confidence = 0.7 + agent.confidence_bias
        
        return DebateVote(
            agent_id=agent.agent_id,
            position_id=chosen,
            confidence=max(0.1, min(1.0, confidence)),
            reasoning=f"Based on {agent.perspective} perspective"
        )
    
    def reach_consensus(
        self,
        method: ConsensusMethod = ConsensusMethod.WEIGHTED
    ) -> ConsensusResult:
        """Attempt to reach consensus among agents."""
        if not self._votes:
            return ConsensusResult(
                method=method,
                reached=False,
                winning_position=None,
                agreement_level=0.0,
                votes=[],
                dissenting_views=[]
            )
        
        # Count votes per position
        vote_counts: Dict[str, float] = {}
        for vote in self._votes:
            if method == ConsensusMethod.WEIGHTED:
                vote_counts[vote.position_id] = vote_counts.get(vote.position_id, 0) + vote.confidence
            else:
                vote_counts[vote.position_id] = vote_counts.get(vote.position_id, 0) + 1
        
        # Find winner
        if not vote_counts:
            return ConsensusResult(
                method=method,
                reached=False,
                winning_position=None,
                agreement_level=0.0,
                votes=self._votes,
                dissenting_views=[]
            )
        
        winner = max(vote_counts.keys(), key=lambda k: vote_counts[k])
        total_votes = sum(vote_counts.values())
        agreement = vote_counts[winner] / total_votes if total_votes > 0 else 0
        
        # Check if consensus is reached
        reached = False
        if method == ConsensusMethod.UNANIMOUS:
            reached = len(vote_counts) == 1
        elif method == ConsensusMethod.SUPERMAJORITY:
            reached = agreement >= 0.67
        elif method == ConsensusMethod.MAJORITY:
            reached = agreement > 0.5
        elif method == ConsensusMethod.WEIGHTED:
            reached = agreement >= 0.6
        
        # Find dissenting views
        dissenting = [
            vote.reasoning
            for vote in self._votes
            if vote.position_id != winner
        ]
        
        return ConsensusResult(
            method=method,
            reached=reached,
            winning_position=winner if reached else None,
            agreement_level=agreement,
            votes=self._votes,
            dissenting_views=dissenting
        )


class ConfidenceAdjuster:
    """Adjusts confidence based on debate and critique."""
    
    def __init__(
        self,
        attack_penalty: float = 0.1,
        support_bonus: float = 0.05,
        consensus_weight: float = 0.3
    ):
        self.attack_penalty = attack_penalty
        self.support_bonus = support_bonus
        self.consensus_weight = consensus_weight
    
    def adjust_from_attacks(
        self,
        base_confidence: float,
        attacks: List[AdversarialAttack]
    ) -> float:
        """Adjust confidence based on successful attacks."""
        if not attacks:
            return base_confidence
        
        # Calculate total attack impact
        total_impact = sum(
            a.strength * a.confidence * self.attack_penalty
            for a in attacks
        )
        
        adjusted = base_confidence - total_impact
        return max(0.1, min(1.0, adjusted))
    
    def adjust_from_structure(
        self,
        base_confidence: float,
        structure: ArgumentStructure,
        scorer: ArgumentQualityScorer
    ) -> float:
        """Adjust confidence based on argument quality."""
        scores = scorer.score_structure(structure)
        quality = scores.get("overall", 0.5)
        
        # Quality affects confidence
        adjustment = (quality - 0.5) * 0.2
        
        adjusted = base_confidence + adjustment
        return max(0.1, min(1.0, adjusted))
    
    def adjust_from_consensus(
        self,
        base_confidence: float,
        consensus: ConsensusResult,
        position_id: str
    ) -> float:
        """Adjust confidence based on debate consensus."""
        if not consensus.reached:
            # No consensus, slight decrease in confidence
            return base_confidence * 0.95
        
        if consensus.winning_position == position_id:
            # Our position won, increase confidence
            boost = consensus.agreement_level * self.consensus_weight
            return min(1.0, base_confidence + boost)
        else:
            # Our position lost, decrease confidence
            penalty = consensus.agreement_level * self.consensus_weight
            return max(0.1, base_confidence - penalty)
    
    def combined_adjustment(
        self,
        base_confidence: float,
        attacks: Optional[List[AdversarialAttack]] = None,
        structure: Optional[ArgumentStructure] = None,
        consensus: Optional[ConsensusResult] = None,
        position_id: Optional[str] = None
    ) -> Tuple[float, Dict[str, float]]:
        """Apply all adjustments and return details."""
        adjustments = {"base": base_confidence}
        current = base_confidence
        
        if attacks:
            current = self.adjust_from_attacks(current, attacks)
            adjustments["after_attacks"] = current
        
        if structure:
            scorer = ArgumentQualityScorer()
            current = self.adjust_from_structure(current, structure, scorer)
            adjustments["after_structure"] = current
        
        if consensus and position_id:
            current = self.adjust_from_consensus(current, consensus, position_id)
            adjustments["after_consensus"] = current
        
        adjustments["final"] = current
        return current, adjustments


class EnhancedDebateSystem:
    """
    Complete enhanced debate system integrating all components.
    """
    
    def __init__(self):
        self.argument_scorer = ArgumentQualityScorer()
        self.adversarial_generator = AdversarialGenerator()
        self.debate = MultiPerspectiveDebate()
        self.confidence_adjuster = ConfidenceAdjuster()
        
        # Add standard debate agents
        self.debate.add_standard_agents()
    
    def analyze_argument(
        self,
        claim: str,
        premises: List[str],
        evidence: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze an argument through adversarial testing.
        
        Returns analysis with quality scores and adjusted confidence.
        """
        # Build argument structure
        builder = ArgumentBuilder(f"arg_{datetime.now().timestamp()}", claim)
        claim_id = builder.add_claim(claim)
        
        for premise in premises:
            builder.add_premise(premise, claim_id)
        
        if evidence:
            for ev in evidence:
                builder.add_evidence(ev, claim_id)
        
        structure = builder.build()
        
        # Score the argument
        quality = self.argument_scorer.score_structure(structure)
        
        # Generate adversarial attacks
        attacks = self.adversarial_generator.generate_attacks(structure)
        
        # Calculate adjusted confidence
        base_confidence = quality["overall"]
        adjusted, details = self.confidence_adjuster.combined_adjustment(
            base_confidence,
            attacks=attacks,
            structure=structure
        )
        
        return {
            "claim": claim,
            "structure": structure,
            "quality_scores": quality,
            "attacks_generated": len(attacks),
            "attacks": [
                {
                    "type": a.attack_type.value,
                    "target": a.target_node_id,
                    "content": a.attack_content,
                    "strength": a.strength
                }
                for a in attacks
            ],
            "base_confidence": base_confidence,
            "adjusted_confidence": adjusted,
            "confidence_adjustments": details
        }
    
    def debate_claim(
        self,
        claim: str,
        supporting_arguments: List[str],
        opposing_arguments: Optional[List[str]] = None,
        rounds: int = 1
    ) -> Dict[str, Any]:
        """
        Conduct a debate on a claim.
        """
        positions = {
            "proponent": claim,
        }
        if opposing_arguments:
            positions["opponent"] = f"Counter to: {claim}"
        
        debate_results = []
        for round_num in range(rounds):
            round_result = self.debate.conduct_round(claim, positions)
            debate_results.append(round_result)
        
        # Reach consensus
        consensus = self.debate.reach_consensus()
        
        return {
            "claim": claim,
            "rounds_conducted": rounds,
            "debate_rounds": debate_results,
            "consensus": {
                "reached": consensus.reached,
                "method": consensus.method.value,
                "winner": consensus.winning_position,
                "agreement_level": consensus.agreement_level,
                "dissenting_views": consensus.dissenting_views
            }
        }
    
    def get_recommendation(
        self,
        analysis: Dict[str, Any],
        threshold: float = 0.6
    ) -> str:
        """Get recommendation based on analysis."""
        confidence = analysis.get("adjusted_confidence", 0.5)
        attacks = analysis.get("attacks_generated", 0)
        quality = analysis.get("quality_scores", {}).get("overall", 0.5)
        
        if confidence >= threshold and quality >= 0.6 and attacks < 3:
            return "ACCEPT: Argument is well-supported with high confidence"
        elif confidence >= threshold * 0.8:
            return "ACCEPT_WITH_CAUTION: Argument is reasonable but has some weaknesses"
        elif confidence >= threshold * 0.6:
            return "NEEDS_REVISION: Argument requires strengthening before acceptance"
        else:
            return "REJECT: Argument has significant weaknesses or low confidence"


# Lightweight classes for test coverage
@dataclass
class ArgumentNode:
    node_id: str
    argument_type: ArgumentType
    content: str
    confidence: float = 0.5
    supports: List[str] = field(default_factory=list)
    attacks: List[str] = field(default_factory=list)
    source: Optional[str] = None


@dataclass
class ArgumentStructure:
    structure_id: str
    main_claim: str
    nodes: Dict[str, ArgumentNode] = field(default_factory=dict)
    root_nodes: List[str] = field(default_factory=list)

    def add_node(self, node: ArgumentNode) -> None:
        self.nodes[node.node_id] = node
        if node.argument_type == ArgumentType.CLAIM and node.node_id not in self.root_nodes:
            self.root_nodes.append(node.node_id)

    def get_supporters(self, node_id: str) -> List[ArgumentNode]:
        return [n for n in self.nodes.values() if node_id in n.supports]

    def get_attackers(self, node_id: str) -> List[ArgumentNode]:
        return [n for n in self.nodes.values() if node_id in n.attacks]

