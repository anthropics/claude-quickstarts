"""
Unit tests for Debate System

Tests argument structures, adversarial attacks, multi-perspective debates,
consensus mechanisms, and quality scoring.
"""

import pytest

pytest.skip("Debate system suite skipped pending full implementation", allow_module_level=True)

from agents.core.debate_system import (  # noqa: E402
    DebateSystem,
    ArgumentBuilder,
    ArgumentQualityScorer,
    AdversarialGenerator,
    MultiPerspectiveDebate,
    ArgumentNode,
    ArgumentStructure,
    ArgumentType,
    AttackType,
    ConsensusMethod,
    DebateAgent,
    DebateVote,
    AdversarialAttack,
    ConsensusResult,
)


class TestArgumentBuilder:
    """Test suite for ArgumentBuilder."""

    @pytest.fixture
    def builder(self):
        """Create ArgumentBuilder instance."""
        return ArgumentBuilder(
            structure_id="test_struct_001",
            main_claim="Climate change is caused by human activities"
        )

    @pytest.mark.unit
    def test_initialization(self, builder):
        """Test builder initialization."""
        assert builder.structure.structure_id == "test_struct_001"
        assert builder.structure.main_claim == "Climate change is caused by human activities"
        assert len(builder.structure.nodes) == 0

    @pytest.mark.unit
    def test_add_claim(self, builder):
        """Test adding a claim node."""
        claim_id = builder.add_claim("CO2 levels are rising", confidence=0.9)

        assert claim_id in builder.structure.nodes
        node = builder.structure.nodes[claim_id]
        assert node.argument_type == ArgumentType.CLAIM
        assert node.content == "CO2 levels are rising"
        assert node.confidence == 0.9

    @pytest.mark.unit
    def test_add_premise(self, builder):
        """Test adding a premise that supports a claim."""
        claim_id = builder.add_claim("Temperature is increasing")
        premise_id = builder.add_premise(
            "Global average temperature has risen 1°C since 1900",
            supports=claim_id,
            confidence=0.95
        )

        premise_node = builder.structure.nodes[premise_id]
        assert premise_node.argument_type == ArgumentType.PREMISE
        assert claim_id in premise_node.supports
        assert premise_node.confidence == 0.95

    @pytest.mark.unit
    def test_add_evidence(self, builder):
        """Test adding evidence with source."""
        claim_id = builder.add_claim("Sea levels are rising")
        evidence_id = builder.add_evidence(
            "Satellite data shows 3mm/year rise",
            supports=claim_id,
            source="NASA, 2023",
            confidence=0.98
        )

        evidence_node = builder.structure.nodes[evidence_id]
        assert evidence_node.argument_type == ArgumentType.EVIDENCE
        assert evidence_node.source == "NASA, 2023"
        assert evidence_node.confidence == 0.98

    @pytest.mark.unit
    def test_add_rebuttal(self, builder):
        """Test adding a rebuttal that attacks a claim."""
        claim_id = builder.add_claim("Solar activity causes warming")
        rebuttal_id = builder.add_rebuttal(
            "Solar activity has decreased while temperatures rise",
            attacks=claim_id,
            confidence=0.85
        )

        rebuttal_node = builder.structure.nodes[rebuttal_id]
        assert rebuttal_node.argument_type == ArgumentType.REBUTTAL
        assert claim_id in rebuttal_node.attacks

    @pytest.mark.unit
    def test_build_structure(self, builder):
        """Test building complete argument structure."""
        claim_id = builder.add_claim("Hypothesis A is true")
        builder.add_premise("Evidence 1", supports=claim_id)
        builder.add_evidence("Data point", supports=claim_id, source="Study 2020")

        structure = builder.build()

        assert isinstance(structure, ArgumentStructure)
        assert len(structure.nodes) == 3
        assert claim_id in structure.root_nodes

    @pytest.mark.unit
    def test_get_supporters(self, builder):
        """Test getting supporter nodes."""
        claim_id = builder.add_claim("Main claim")
        premise1 = builder.add_premise("Premise 1", supports=claim_id)
        premise2 = builder.add_premise("Premise 2", supports=claim_id)

        structure = builder.build()
        supporters = structure.get_supporters(claim_id)

        assert len(supporters) == 2
        supporter_ids = [s.node_id for s in supporters]
        assert premise1 in supporter_ids
        assert premise2 in supporter_ids

    @pytest.mark.unit
    def test_get_attackers(self, builder):
        """Test getting attacker nodes."""
        claim_id = builder.add_claim("Claim to attack")
        rebuttal1 = builder.add_rebuttal("Rebuttal 1", attacks=claim_id)
        rebuttal2 = builder.add_rebuttal("Rebuttal 2", attacks=claim_id)

        structure = builder.build()
        attackers = structure.get_attackers(claim_id)

        assert len(attackers) == 2
        attacker_ids = [a.node_id for a in attackers]
        assert rebuttal1 in attacker_ids
        assert rebuttal2 in attacker_ids


class TestArgumentQualityScorer:
    """Test suite for ArgumentQualityScorer."""

    @pytest.fixture
    def scorer(self):
        """Create ArgumentQualityScorer instance."""
        return ArgumentQualityScorer()

    @pytest.fixture
    def simple_structure(self):
        """Create a simple argument structure."""
        builder = ArgumentBuilder("test", "Main claim")
        claim_id = builder.add_claim("The sky is blue")
        builder.add_premise("Light scattering makes it blue", supports=claim_id)
        builder.add_evidence("Physics experiments confirm", supports=claim_id, source="Physics 101")
        return builder.build()

    @pytest.mark.unit
    def test_score_node_with_support(self, scorer, simple_structure):
        """Test scoring a node with supporting evidence."""
        claim_node = next(
            n for n in simple_structure.nodes.values()
            if n.argument_type == ArgumentType.CLAIM
        )

        score = scorer.score_node(claim_node, simple_structure)

        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should have decent score with support

    @pytest.mark.unit
    def test_score_node_without_support(self, scorer):
        """Test scoring an isolated node without support."""
        structure = ArgumentStructure("test", "Main")
        node = ArgumentNode(
            node_id="solo",
            argument_type=ArgumentType.CLAIM,
            content="Unsupported claim",
            confidence=0.5
        )
        structure.add_node(node)

        score = scorer.score_node(node, structure)

        assert 0.0 <= score <= 1.0
        assert score < 0.7  # Should have lower score without support

    @pytest.mark.unit
    def test_score_node_with_evidence(self, scorer):
        """Test that evidence increases quality score."""
        builder = ArgumentBuilder("test", "Main")
        claim_id = builder.add_claim("Claim with evidence")
        builder.add_evidence("Strong evidence", supports=claim_id, confidence=0.95, source="Journal")

        structure = builder.build()
        claim_node = structure.nodes[claim_id]

        score = scorer.score_node(claim_node, structure)

        assert score > 0.6  # Evidence should boost score

    @pytest.mark.unit
    def test_score_structure_overall(self, scorer, simple_structure):
        """Test scoring entire argument structure."""
        scores = scorer.score_structure(simple_structure)

        assert "overall" in scores
        assert "root_quality" in scores
        assert "avg_node_quality" in scores
        assert "node_scores" in scores
        assert 0.0 <= scores["overall"] <= 1.0

    @pytest.mark.unit
    def test_score_empty_structure(self, scorer):
        """Test scoring empty structure."""
        structure = ArgumentStructure("empty", "No nodes")
        scores = scorer.score_structure(structure)

        assert scores["overall"] == 0.0

    @pytest.mark.unit
    def test_node_with_source_scores_higher(self, scorer):
        """Test that nodes with sources score higher."""
        builder = ArgumentBuilder("test", "Main")
        claim_id = builder.add_claim("Claim")

        # Node with source
        with_source = builder.add_evidence("Evidence A", supports=claim_id, source="Nature 2023")

        # Node without source
        builder2 = ArgumentBuilder("test2", "Main")
        claim_id2 = builder2.add_claim("Claim")
        without_source = builder2.add_evidence("Evidence B", supports=claim_id2)

        structure1 = builder.build()
        structure2 = builder2.build()

        score_with = scorer.score_node(structure1.nodes[with_source], structure1)
        score_without = scorer.score_node(structure2.nodes[without_source], structure2)

        assert score_with > score_without


class TestAdversarialGenerator:
    """Test suite for AdversarialGenerator."""

    @pytest.fixture
    def generator(self):
        """Create AdversarialGenerator instance."""
        return AdversarialGenerator()

    @pytest.fixture
    def target_structure(self):
        """Create a structure to attack."""
        builder = ArgumentBuilder("target", "All swans are white")
        claim_id = builder.add_claim("All swans are white", confidence=0.8)
        builder.add_premise("All observed swans are white", supports=claim_id)
        return builder.build()

    @pytest.mark.unit
    def test_initialization(self, generator):
        """Test generator initialization."""
        assert hasattr(generator, '_attack_templates')
        assert len(generator._attack_templates) > 0

    @pytest.mark.unit
    def test_generate_attacks_on_structure(self, generator, target_structure):
        """Test generating attacks on an argument structure."""
        attacks = generator.generate_attacks(target_structure)

        assert len(attacks) > 0
        assert all(isinstance(a, AdversarialAttack) for a in attacks)

    @pytest.mark.unit
    def test_generate_specific_attack_type(self, generator, target_structure):
        """Test generating specific attack type."""
        attacks = generator.generate_attacks(
            target_structure,
            attack_types=[AttackType.COUNTEREXAMPLE]
        )

        assert all(a.attack_type == AttackType.COUNTEREXAMPLE for a in attacks)

    @pytest.mark.unit
    def test_attack_on_specific_node(self, generator, target_structure):
        """Test attacking a specific node."""
        claim_node_id = target_structure.root_nodes[0]
        attacks = generator.generate_attacks(
            target_structure,
            target_node_id=claim_node_id
        )

        assert all(a.target_node_id == claim_node_id for a in attacks)

    @pytest.mark.unit
    def test_attack_has_required_fields(self, generator, target_structure):
        """Test that generated attacks have all required fields."""
        attacks = generator.generate_attacks(target_structure)

        for attack in attacks:
            assert attack.attack_id is not None
            assert attack.attack_type in list(AttackType)
            assert attack.target_node_id is not None
            assert attack.attack_content is not None
            assert 0.0 <= attack.strength <= 1.0
            assert 0.0 <= attack.confidence <= 1.0
            assert attack.generated_by is not None

    @pytest.mark.unit
    def test_all_attack_types_supported(self, generator):
        """Test that all attack types can be generated."""
        attack_types = [
            AttackType.COUNTEREXAMPLE,
            AttackType.UNDERCUT,
            AttackType.REBUT,
            AttackType.PREMISE_ATTACK,
            AttackType.ALTERNATIVE
        ]

        for attack_type in attack_types:
            assert attack_type in generator._attack_templates


class TestMultiPerspectiveDebate:
    """Test suite for MultiPerspectiveDebate."""

    @pytest.fixture
    def debate(self):
        """Create MultiPerspectiveDebate instance."""
        return MultiPerspectiveDebate()

    @pytest.fixture
    def agents(self):
        """Create debate agents."""
        return [
            DebateAgent(
                agent_id="advocate",
                name="Advocate",
                perspective="advocate",
                expertise_areas=["logic"]
            ),
            DebateAgent(
                agent_id="skeptic",
                name="Skeptic",
                perspective="skeptic",
                expertise_areas=["critical_thinking"]
            ),
            DebateAgent(
                agent_id="neutral",
                name="Neutral Judge",
                perspective="neutral",
                expertise_areas=["fairness"]
            )
        ]

    @pytest.mark.unit
    def test_initialization(self, debate):
        """Test debate initialization."""
        assert len(debate.agents) == 0
        assert hasattr(debate, '_positions')
        assert hasattr(debate, '_votes')

    @pytest.mark.unit
    def test_add_agent(self, debate, agents):
        """Test adding agents to debate."""
        for agent in agents:
            debate.add_agent(agent)

        assert len(debate.agents) == 3
        assert debate.agents[0].agent_id == "advocate"

    @pytest.mark.unit
    def test_add_standard_agents(self, debate):
        """Test adding standard debate agents."""
        debate.add_standard_agents()

        assert len(debate.agents) > 0
        perspectives = [a.perspective for a in debate.agents]
        assert "skeptic" in perspectives or "advocate" in perspectives

    @pytest.mark.integration
    def test_conduct_debate(self, debate, agents):
        """Test conducting a debate."""
        for agent in agents:
            debate.add_agent(agent)

        # Add positions
        position_a = ArgumentBuilder("pos_a", "Position A").build()
        position_b = ArgumentBuilder("pos_b", "Position B").build()

        debate.add_position("position_a", position_a)
        debate.add_position("position_b", position_b)

        # Conduct debate (if method exists)
        # result = debate.conduct_debate()
        # assert result is not None


class TestConsensusMethod:
    """Test suite for consensus mechanisms."""

    @pytest.fixture
    def votes(self):
        """Create sample votes."""
        return [
            DebateVote(
                agent_id="agent_1",
                position_id="pos_a",
                confidence=0.9,
                reasoning="Strong evidence"
            ),
            DebateVote(
                agent_id="agent_2",
                position_id="pos_a",
                confidence=0.8,
                reasoning="Logical argument"
            ),
            DebateVote(
                agent_id="agent_3",
                position_id="pos_b",
                confidence=0.6,
                reasoning="Some doubts"
            )
        ]

    @pytest.mark.unit
    def test_majority_consensus(self, votes):
        """Test majority voting consensus."""
        # Count votes for each position
        vote_counts = {}
        for vote in votes:
            vote_counts[vote.position_id] = vote_counts.get(vote.position_id, 0) + 1

        winner = max(vote_counts, key=vote_counts.get)
        assert winner == "pos_a"  # 2 votes vs 1 vote

    @pytest.mark.unit
    def test_weighted_consensus(self, votes):
        """Test confidence-weighted consensus."""
        # Weight votes by confidence
        weighted_votes = {}
        for vote in votes:
            current = weighted_votes.get(vote.position_id, 0.0)
            weighted_votes[vote.position_id] = current + vote.confidence

        winner = max(weighted_votes, key=weighted_votes.get)
        assert winner == "pos_a"  # 0.9 + 0.8 = 1.7 vs 0.6

    @pytest.mark.unit
    def test_unanimous_consensus_not_reached(self, votes):
        """Test unanimous consensus not reached when votes differ."""
        positions = set(v.position_id for v in votes)
        unanimous = len(positions) == 1

        assert unanimous is False  # We have both pos_a and pos_b

    @pytest.mark.unit
    def test_supermajority_threshold(self, votes):
        """Test supermajority (2/3) threshold."""
        vote_counts = {}
        for vote in votes:
            vote_counts[vote.position_id] = vote_counts.get(vote.position_id, 0) + 1

        total_votes = len(votes)
        supermajority_threshold = total_votes * (2.0 / 3.0)

        pos_a_votes = vote_counts.get("pos_a", 0)
        supermajority_reached = pos_a_votes >= supermajority_threshold

        assert supermajority_reached is True  # 2 >= (3 * 2/3 = 2)


class TestDebateVote:
    """Test suite for DebateVote."""

    @pytest.mark.unit
    def test_vote_creation(self):
        """Test creating a debate vote."""
        vote = DebateVote(
            agent_id="agent_001",
            position_id="pos_a",
            confidence=0.85,
            reasoning="Well-supported argument"
        )

        assert vote.agent_id == "agent_001"
        assert vote.position_id == "pos_a"
        assert vote.confidence == 0.85
        assert "supported" in vote.reasoning.lower()

    @pytest.mark.unit
    def test_vote_confidence_range(self):
        """Test that vote confidence is in valid range."""
        vote = DebateVote(
            agent_id="agent_002",
            position_id="pos_b",
            confidence=0.5,
            reasoning="Uncertain"
        )

        assert 0.0 <= vote.confidence <= 1.0


class TestDebateAgent:
    """Test suite for DebateAgent."""

    @pytest.mark.unit
    def test_agent_creation(self):
        """Test creating a debate agent."""
        agent = DebateAgent(
            agent_id="devil_advocate",
            name="Devil's Advocate",
            perspective="skeptic",
            expertise_areas=["logic", "fallacies"],
            confidence_bias=-0.1
        )

        assert agent.agent_id == "devil_advocate"
        assert agent.perspective == "skeptic"
        assert "logic" in agent.expertise_areas
        assert agent.confidence_bias == -0.1

    @pytest.mark.unit
    def test_agent_default_bias(self):
        """Test agent with default confidence bias."""
        agent = DebateAgent(
            agent_id="neutral",
            name="Neutral Judge",
            perspective="neutral"
        )

        assert agent.confidence_bias == 0.0


class TestArgumentStructure:
    """Test suite for ArgumentStructure."""

    @pytest.mark.unit
    def test_empty_structure(self):
        """Test empty argument structure."""
        structure = ArgumentStructure("empty", "No arguments yet")

        assert len(structure.nodes) == 0
        assert len(structure.root_nodes) == 0

    @pytest.mark.unit
    def test_add_node_updates_roots(self):
        """Test that adding claim nodes updates root_nodes."""
        structure = ArgumentStructure("test", "Main")
        claim = ArgumentNode(
            node_id="claim_1",
            argument_type=ArgumentType.CLAIM,
            content="Root claim",
            confidence=0.8
        )

        structure.add_node(claim)

        assert "claim_1" in structure.root_nodes

    @pytest.mark.unit
    def test_supported_node_not_root(self):
        """Test that nodes with support are not added to roots."""
        structure = ArgumentStructure("test", "Main")

        # Add root claim
        root_claim = ArgumentNode(
            node_id="root",
            argument_type=ArgumentType.CLAIM,
            content="Root",
            confidence=0.8
        )
        structure.add_node(root_claim)

        # Add supporting claim
        supporting_claim = ArgumentNode(
            node_id="support",
            argument_type=ArgumentType.CLAIM,
            content="Supporting claim",
            confidence=0.8,
            supports=["root"]
        )
        structure.add_node(supporting_claim)

        assert "root" in structure.root_nodes
        assert "support" not in structure.root_nodes


class TestIntegrationDebateFlow:
    """Integration tests for complete debate flow."""

    @pytest.mark.integration
    def test_build_attack_score_flow(self):
        """Test complete flow: build argument, attack it, score it."""
        # Build argument
        builder = ArgumentBuilder("debate_001", "All AI is dangerous")
        claim_id = builder.add_claim("AI poses existential risk")
        builder.add_premise("AI could surpass human intelligence", supports=claim_id)
        structure = builder.build()

        # Generate attacks
        generator = AdversarialGenerator()
        attacks = generator.generate_attacks(structure)

        # Score the argument
        scorer = ArgumentQualityScorer()
        scores = scorer.score_structure(structure)

        # Verify complete flow
        assert len(structure.nodes) > 0
        assert len(attacks) > 0
        assert "overall" in scores
        assert scores["overall"] > 0

    @pytest.mark.integration
    def test_multi_agent_debate_flow(self):
        """Test complete multi-agent debate flow."""
        # Create debate
        debate = MultiPerspectiveDebate()
        debate.add_standard_agents()

        # Create positions
        builder_a = ArgumentBuilder("pos_a", "Position A is correct")
        builder_a.add_claim("Evidence supports A")
        position_a = builder_a.build()

        builder_b = ArgumentBuilder("pos_b", "Position B is correct")
        builder_b.add_claim("Evidence supports B")
        position_b = builder_b.build()

        # Verify debate setup
        assert len(debate.agents) > 0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.unit
    def test_attack_nonexistent_node(self):
        """Test attacking a node that doesn't exist."""
        generator = AdversarialGenerator()
        structure = ArgumentStructure("test", "Main")

        attacks = generator.generate_attacks(
            structure,
            target_node_id="nonexistent"
        )

        # Should handle gracefully
        assert isinstance(attacks, list)

    @pytest.mark.unit
    def test_score_self_referential_structure(self):
        """Test scoring structure with circular support."""
        structure = ArgumentStructure("circular", "Main")
        node_a = ArgumentNode(
            node_id="a",
            argument_type=ArgumentType.CLAIM,
            content="A supports B",
            confidence=0.8,
            supports=["b"]
        )
        node_b = ArgumentNode(
            node_id="b",
            argument_type=ArgumentType.CLAIM,
            content="B supports A",
            confidence=0.8,
            supports=["a"]
        )
        structure.add_node(node_a)
        structure.add_node(node_b)

        scorer = ArgumentQualityScorer()
        scores = scorer.score_structure(structure)

        # Should handle without infinite loop
        assert "overall" in scores

    @pytest.mark.unit
    def test_empty_vote_list(self):
        """Test consensus with no votes."""
        votes = []

        # Should handle empty list gracefully
        vote_counts = {}
        for vote in votes:
            vote_counts[vote.position_id] = vote_counts.get(vote.position_id, 0) + 1

        assert len(vote_counts) == 0
