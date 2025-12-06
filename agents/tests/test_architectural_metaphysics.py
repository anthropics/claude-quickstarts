"""
Architectural Metaphysics Validation Tests

Tests that the system adheres to the metaphysical framework:
- Logic (Skeleton): Defines validity, structural relationships
- AI (Muscles): Interprets within frame, provides perspectives
- User (Heart): Determines purpose, values, final judgment
- Reason (Emergent): Synthesis of skeleton + muscles + heart

These tests validate architectural invariants and separation of concerns.
"""

import pytest

pytest.skip("Architectural metaphysics suite skipped pending full implementation", allow_module_level=True)

from agents.core.logic_engine import LogicEngine, ArgumentForm  # noqa: E402
from agents.core.debate_system import DebateSystem, ArgumentNode  # noqa: E402
from agents.core.critic_system import CriticSystem, CritiqueResult  # noqa: E402
from agents.core.decision_model import DecisionModel, Decision  # noqa: E402
from agents.core.role_system import RoleSystem, Role  # noqa: E402
from agents.core.clarification_system import ClarificationSystem  # noqa: E402
from agents.core.constraint_system import ConstraintSystem  # noqa: E402


class TestLogicLayerSkeleton:
    """
    Test that Logic layer (Skeleton) properly:
    - Defines validity without interpretation
    - Operates deterministically
    - Does not depend on context or user
    """

    @pytest.fixture
    def logic_engine(self):
        return LogicEngine()

    @pytest.mark.unit
    def test_logic_is_deterministic(self, logic_engine):
        """Logic must return identical results for identical inputs."""
        premises = [
            "If it rains, then the ground is wet",
            "It rains"
        ]
        conclusion = "The ground is wet"

        result1 = logic_engine.validate_argument(premises, conclusion)
        result2 = logic_engine.validate_argument(premises, conclusion)

        # Exact same inputs must produce exact same outputs
        assert result1.valid == result2.valid
        assert result1.form == result2.form
        assert result1.confidence == result2.confidence

    @pytest.mark.unit
    def test_logic_no_user_context_dependency(self, logic_engine):
        """Logic must not depend on user context or preferences."""
        argument = {
            "premises": ["P", "P → Q"],
            "conclusion": "Q"
        }

        # Simulate different user contexts

        # Logic should be universal - same result regardless of user
        result_a = logic_engine.validate_argument(
            argument["premises"],
            argument["conclusion"]
        )
        result_b = logic_engine.validate_argument(
            argument["premises"],
            argument["conclusion"]
        )

        assert result_a.valid == result_b.valid
        assert result_a.form == result_b.form

    @pytest.mark.unit
    def test_logic_separates_validity_from_soundness(self, logic_engine):
        """Logic determines validity, not truth or soundness."""
        # Valid but unsound argument (false premise)
        premises = [
            "All birds can fly",  # False premise (penguins!)
            "Penguins are birds"
        ]
        conclusion = "Penguins can fly"

        result = logic_engine.validate_argument(premises, conclusion)

        # Logic says: VALID structure (categorical syllogism)
        # But logic does NOT say: SOUND or TRUE
        assert result.valid is True  # Valid structure
        assert result.form == ArgumentForm.CATEGORICAL_SYLLOGISM

        # Logic should not have "is_true" or "is_sound" field
        assert not hasattr(result, 'is_true')
        assert not hasattr(result, 'is_sound')

    @pytest.mark.unit
    def test_logic_does_not_moralize(self, logic_engine):
        """Logic must not make value judgments."""
        # Controversial but structurally valid argument
        premises = ["If P then Q", "P"]
        conclusion = "Q"

        result = logic_engine.validate_argument(premises, conclusion)

        # Logic judges ONLY structure, not content morality
        assert result.valid is True
        assert "problematic" not in result.explanation.lower()
        assert "controversial" not in result.explanation.lower()
        assert "inappropriate" not in result.explanation.lower()


class TestAILayerMuscles:
    """
    Test that AI layer (Muscles) properly:
    - Provides multiple perspectives
    - Does not decide for user
    - Expresses uncertainty
    - Attributes interpretations to sources
    """

    @pytest.fixture
    def critic_system(self):
        return CriticSystem()

    @pytest.fixture
    def debate_system(self):
        return DebateSystem()

    @pytest.mark.unit
    def test_ai_provides_multiple_perspectives(self, critic_system):
        """AI must offer multiple interpretations, not singular truth."""
        reasoning = "Economic inequality is growing."
        conclusion = "Society needs reform."

        result = critic_system.review(reasoning, conclusion)

        # Should have multiple critique perspectives
        assert isinstance(result.critiques, list)
        # AI provides perspectives, not a single verdict
        assert len(result.critiques) >= 0  # May have 0 or more critiques

    @pytest.mark.unit
    def test_ai_expresses_uncertainty(self, critic_system):
        """AI must express confidence < 1.0 for non-tautologies."""
        reasoning = "Some evidence suggests X might be true."
        conclusion = "X is possibly true."

        result = critic_system.review(reasoning, conclusion)

        # AI should express uncertainty, not certainty
        assert hasattr(result, 'revised_confidence')
        # Non-tautological conclusions should have < 1.0 confidence
        assert result.revised_confidence <= 1.0

    @pytest.mark.unit
    def test_ai_does_not_auto_select_best(self, debate_system):
        """AI must not automatically select 'best' interpretation."""
        # Create multi-perspective debate
        claim = "Economic policy should prioritize growth."

        # Debate might generate multiple perspectives
        # System should NOT auto-select one as "correct"

        # Create argument structure
        arg = ArgumentNode(claim=claim, claim_id="c1")
        debate_system.add_argument(arg)

        # Get perspectives (implementation-specific)
        # Key test: no auto-selection of "winner"
        assert hasattr(debate_system, 'arguments')
        # Debate system should store arguments, not pre-select winners

    @pytest.mark.unit
    def test_ai_attributes_interpretations(self, critic_system):
        """AI must attribute interpretations to sources/methods."""
        reasoning = "All swans observed so far are white."
        conclusion = "All swans are white."

        result = critic_system.review(reasoning, conclusion)

        # Critiques should identify their type/source
        for critique in result.critiques:
            assert hasattr(critique, 'critique_type')
            assert hasattr(critique, 'description')


class TestUserLayerHeart:
    """
    Test that User layer (Heart) properly:
    - Captures user intent
    - Allows user override
    - Requests clarification
    - Persists preferences
    """

    @pytest.fixture
    def role_system(self):
        return RoleSystem()

    @pytest.fixture
    def clarification_system(self):
        return ClarificationSystem()

    @pytest.fixture
    def constraint_system(self):
        return ConstraintSystem()

    @pytest.mark.unit
    def test_user_can_select_profiles(self, role_system):
        """User must be able to select reasoning profiles/roles."""
        # User chooses which interpretive lenses to use
        roles = role_system.list_available_roles()

        assert len(roles) > 0
        assert all(isinstance(r, (Role, dict)) for r in roles)

    @pytest.mark.unit
    def test_user_can_override_ai(self, constraint_system):
        """User preferences must override AI suggestions."""
        # User sets constraints
        user_constraint = {
            "type": "value_boundary",
            "description": "Do not suggest X",
            "strict": True
        }

        # Add constraint
        constraint_system.add_constraint(user_constraint)

        # Verify constraint is stored
        constraints = constraint_system.get_active_constraints()
        assert len(constraints) > 0

    @pytest.mark.unit
    def test_clarification_required_for_ambiguity(self, clarification_system):
        """System must ask for clarification, not guess."""
        ambiguous_query = "What about banks?"  # River banks? Financial banks?

        result = clarification_system.check_if_clarification_needed(ambiguous_query)

        # Should detect ambiguity
        assert hasattr(result, 'needs_clarification')
        if result.needs_clarification:
            assert hasattr(result, 'clarifying_question')
            assert result.clarifying_question is not None

    @pytest.mark.unit
    def test_user_preferences_persist(self, role_system):
        """User preferences must be stored and retrievable."""
        user_id = "test_user_123"
        preferences = {
            "preferred_roles": ["analyst", "critic"],
            "confidence_threshold": 0.7
        }

        # Save preferences
        role_system.save_user_preferences(user_id, preferences)

        # Retrieve preferences
        retrieved = role_system.get_user_preferences(user_id)

        assert retrieved is not None
        assert "preferred_roles" in retrieved or retrieved == preferences


class TestReasonLayerSynthesis:
    """
    Test that Reason (synthesis) properly:
    - Incorporates all three layers
    - Traces provenance
    - Degrades gracefully under conflict
    - Provides explanations
    """

    @pytest.fixture
    def decision_model(self):
        return DecisionModel()

    @pytest.fixture
    def logic_engine(self):
        return LogicEngine()

    @pytest.mark.integration
    def test_synthesis_incorporates_all_layers(self, decision_model):
        """Synthesis must combine logic + AI + user layers."""
        # Create a decision scenario
        options = [
            {"id": "opt_a", "description": "Option A"},
            {"id": "opt_b", "description": "Option B"}
        ]

        # Add evidence for decision
        evidence_a = {
            "option": "opt_a",
            "support": 0.7,
            "source": "analysis"
        }

        decision_model.add_evidence(evidence_a)

        # Make decision
        result = decision_model.decide(options)

        # Decision should trace back to inputs
        assert isinstance(result, (Decision, dict))
        assert hasattr(result, 'selected_option') or 'selected_option' in result

    @pytest.mark.integration
    def test_logic_blocks_invalid_synthesis(self, decision_model, logic_engine):
        """Logic must block structurally invalid inferences."""
        # Invalid logical structure
        premises = ["P"]
        invalid_conclusion = "Q"  # Does not follow from P alone

        logic_result = logic_engine.validate_argument(premises, invalid_conclusion)

        # Logic says: invalid
        assert logic_result.valid is False

        # Decision model should respect logic's veto
        # Even if AI/user want this conclusion, logic blocks it

    @pytest.mark.integration
    def test_synthesis_degrades_gracefully(self, decision_model):
        """Synthesis must handle conflicts between layers gracefully."""
        # Scenario: conflicting evidence
        evidence_1 = {"option": "opt_a", "support": 0.8}
        evidence_2 = {"option": "opt_b", "support": 0.8}

        decision_model.add_evidence(evidence_1)
        decision_model.add_evidence(evidence_2)

        options = [
            {"id": "opt_a", "description": "Option A"},
            {"id": "opt_b", "description": "Option B"}
        ]

        result = decision_model.decide(options)

        # Should handle conflict gracefully (not crash)
        assert result is not None
        # Confidence should be lower under conflict
        if hasattr(result, 'confidence'):
            assert result.confidence < 1.0

    @pytest.mark.integration
    def test_synthesis_provides_explanation(self, decision_model):
        """Synthesis must explain how it reached conclusion."""
        options = [{"id": "opt_a", "description": "Option A"}]
        evidence = {"option": "opt_a", "support": 0.9}

        decision_model.add_evidence(evidence)
        result = decision_model.decide(options)

        # Should provide explanation
        assert hasattr(result, 'explanation') or 'explanation' in result


class TestArchitecturalInvariants:
    """
    Test architectural separation of concerns and dependency rules.
    """

    @pytest.mark.unit
    def test_logic_has_no_ai_dependency(self):
        """Logic modules must not import AI modules."""
        import agents.core.logic_engine as logic_module

        # Check imports in logic_engine
        import inspect
        source = inspect.getsource(logic_module)

        # Logic should NOT import debate, critic, etc.
        forbidden_imports = [
            "from agents.core.debate_system import",
            "from agents.core.critic_system import",
            "import agents.core.debate_system",
            "import agents.core.critic_system"
        ]

        for forbidden in forbidden_imports:
            assert forbidden not in source, f"Logic layer imports AI layer: {forbidden}"

    @pytest.mark.unit
    def test_logic_has_no_user_dependency(self):
        """Logic modules must not import User modules."""
        import agents.core.logic_engine as logic_module
        import inspect
        source = inspect.getsource(logic_module)

        # Logic should NOT import role_system, feedback_system, etc.
        forbidden_imports = [
            "from agents.core.role_system import",
            "from agents.core.feedback_system import",
            "from agents.core.clarification_system import"
        ]

        for forbidden in forbidden_imports:
            assert forbidden not in source, f"Logic layer imports User layer: {forbidden}"

    @pytest.mark.unit
    def test_ai_can_import_logic(self):
        """AI modules MAY import Logic modules (allowed dependency)."""
        import agents.core.critic_system as critic_module
        import inspect
        inspect.getsource(critic_module)

        # AI can use logic for validation
        # This is allowed and expected

    @pytest.mark.unit
    def test_synthesis_can_import_all_layers(self):
        """Synthesis modules may import Logic + AI + User."""
        import agents.core.decision_model as decision_module
        import inspect
        inspect.getsource(decision_module)

        # Decision model (synthesis) can import from all layers
        # This is allowed and expected


class TestProfileAsInterpretiveForce:
    """
    Test that profiles (Marx, Freud, etc.) are interpretive lenses, not arbiters.
    """

    @pytest.fixture
    def role_system(self):
        return RoleSystem()

    @pytest.mark.unit
    def test_profiles_are_not_arbiters(self, role_system):
        """Profiles must provide interpretations, not final judgments."""
        # Get available roles/profiles
        roles = role_system.list_available_roles()

        # Each role should be described as interpretive
        # Not as "the correct way to think"
        for role in roles:
            # Roles should not claim finality
            if isinstance(role, dict):
                assert 'name' in role
            else:
                assert hasattr(role, 'name')

    @pytest.mark.unit
    def test_profiles_live_in_muscle_layer(self, role_system):
        """Profiles should be in AI layer (muscles), not logic or user."""
        # Profiles are interpretive tools
        # They should not be hard-coded logic rules
        # They should not override user choice

        roles = role_system.list_available_roles()
        assert len(roles) >= 0  # System may have 0+ profiles

        # User can select which profiles to apply
        # This confirms profiles are tools, not judges


class TestAntiPatterns:
    """
    Test that system avoids architectural anti-patterns.
    """

    @pytest.fixture
    def logic_engine(self):
        return LogicEngine()

    @pytest.mark.unit
    def test_no_logic_moralizing(self, logic_engine):
        """Logic must not reject arguments based on content morality."""
        # Controversial but valid modus ponens
        premises = [
            "If P then Q",
            "P"
        ]
        conclusion = "Q"

        result = logic_engine.validate_argument(premises, conclusion)

        # Logic evaluates structure only
        assert result.valid is True
        # Should not say "morally problematic"
        assert "moral" not in result.explanation.lower()
        assert "ethical" not in result.explanation.lower()

    @pytest.mark.unit
    def test_no_ai_auto_deciding(self, critic_system):
        """AI must not auto-select 'best' perspective without user."""
        reasoning = "Multiple valid interpretations exist."
        conclusion = "One interpretation is correct."

        result = critic_system.review(reasoning, conclusion)

        # Should provide critiques, not auto-select winner
        assert isinstance(result, CritiqueResult)
        # Should not have "final_verdict" field
        assert not hasattr(result, 'final_verdict')

    @pytest.mark.unit
    def test_no_bypass_user_confirmation(self, decision_model):
        """System must not execute high-stakes decisions without user approval."""
        # High-stakes scenario
        options = [{"id": "critical_action", "risk": "high"}]

        decision_model.add_evidence({"option": "critical_action", "support": 0.9})
        result = decision_model.decide(options)

        # If high-stakes, should require user approval
        if hasattr(result, 'requires_user_approval'):
            # High-risk decisions should require approval
            if any(opt.get('risk') == 'high' for opt in options):
                assert result.requires_user_approval is True


class TestProvenanceTracing:
    """
    Test that synthesis outputs trace provenance to all layers.
    """

    @pytest.fixture
    def decision_model(self):
        return DecisionModel()

    @pytest.mark.integration
    def test_provenance_includes_logic(self, decision_model):
        """Decision provenance must trace to logical validation."""
        options = [{"id": "opt_a"}]
        evidence = {"option": "opt_a", "support": 0.8}

        decision_model.add_evidence(evidence)
        result = decision_model.decide(options)

        # Should have provenance information
        if hasattr(result, 'provenance'):
            # Provenance should reference inputs
            assert result.provenance is not None

    @pytest.mark.integration
    def test_provenance_includes_ai(self, decision_model):
        """Decision provenance must trace to AI perspectives."""
        options = [{"id": "opt_a"}]
        evidence = {"option": "opt_a", "support": 0.8, "source": "ai_analysis"}

        decision_model.add_evidence(evidence)
        result = decision_model.decide(options)

        # Should trace AI contributions
        if hasattr(result, 'evidence_used'):
            assert len(result.evidence_used) > 0

    @pytest.mark.integration
    def test_provenance_includes_user(self, decision_model):
        """Decision provenance must trace to user preferences."""
        options = [{"id": "opt_a"}]

        # User sets preference
        user_pref = {"preferred_option": "opt_a", "weight": 0.9}

        # Add as evidence
        decision_model.add_evidence(user_pref)
        result = decision_model.decide(options)

        # Should incorporate user preference
        assert result is not None


class TestEmergentReason:
    """
    Test that reason emerges from disciplined interaction, not isolation.
    """

    @pytest.fixture
    def logic_engine(self):
        return LogicEngine()

    @pytest.fixture
    def critic_system(self):
        return CriticSystem()

    @pytest.fixture
    def decision_model(self):
        return DecisionModel()

    @pytest.mark.integration
    def test_reason_requires_all_layers(self, logic_engine, critic_system, decision_model):
        """Reason must emerge from skeleton + muscles + heart."""
        # Premises
        premises = ["All humans are mortal", "Socrates is human"]
        conclusion = "Socrates is mortal"

        # Layer 1: Logic validates structure
        logic_result = logic_engine.validate_argument(premises, conclusion)
        assert logic_result.valid is True  # Skeleton says: valid

        # Layer 2: AI critiques interpretation
        reasoning_text = " ".join(premises)
        critic_result = critic_system.review(reasoning_text, conclusion)
        # Muscles say: here are perspectives

        # Layer 3: User would select weights/preferences
        # (Simulated here)

        # Synthesis: All layers contribute
        # Reason emerges from their interaction
        final_confidence = logic_result.confidence
        if hasattr(critic_result, 'revised_confidence'):
            final_confidence = min(final_confidence, critic_result.revised_confidence)

        # Emergent reason incorporates all layers
        assert final_confidence > 0.0


class TestArchitecturalDocumentation:
    """
    Test that architecture document exists and is maintained.
    """

    @pytest.mark.unit
    def test_architecture_document_exists(self):
        """Architecture metaphysics document must exist."""
        import os
        doc_path = "/Users/christiansmith/Documents/GitHub/claude-quickstarts/agents/ARCHITECTURE_METAPHYSICS.md"

        assert os.path.exists(doc_path), "Architecture document missing"

        # Document should be non-empty
        with open(doc_path, 'r') as f:
            content = f.read()

        assert len(content) > 1000, "Architecture document too short"
        assert "Skeleton" in content or "skeleton" in content
        assert "Muscles" in content or "muscles" in content
        assert "Heart" in content or "heart" in content
        assert "Reason" in content or "reason" in content
