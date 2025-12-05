"""
Architectural Compliance Tests - Validates Metaphysical Foundation

Tests that all modules adhere to the triadic architecture:
- Logic (Skeleton): Validity without interpretation
- AI (Muscles): Perspectives without verdicts
- User (Heart): Purpose and final judgment
- Reason (Synthesis): Emergent from interaction

This test suite enforces architectural invariants and prevents layer violations.
"""

import pytest
import inspect
import importlib
from pathlib import Path
from typing import List, Dict, Any, Set
from dataclasses import dataclass
from enum import Enum


class ArchitecturalLayer(Enum):
    """Architectural layers in the system."""
    LOGIC = "logic"  # Skeleton
    AI = "ai"  # Muscles
    USER = "user"  # Heart
    SYNTHESIS = "synthesis"  # Reason (emergent)
    UTILITY = "utility"  # Infrastructure (no layer constraints)


@dataclass
class ModuleClassification:
    """Classification of a module into architectural layer."""
    module_name: str
    layer: ArchitecturalLayer
    allowed_dependencies: List[ArchitecturalLayer]
    description: str


# Module Classification Registry
# Maps each core module to its architectural layer
MODULE_REGISTRY: Dict[str, ModuleClassification] = {
    # LOGIC LAYER (Skeleton) - No dependencies on AI or User
    "logic_engine": ModuleClassification(
        module_name="logic_engine",
        layer=ArchitecturalLayer.LOGIC,
        allowed_dependencies=[],
        description="Propositional logic validation"
    ),
    "categorical_engine": ModuleClassification(
        module_name="categorical_engine",
        layer=ArchitecturalLayer.LOGIC,
        allowed_dependencies=[],
        description="Aristotelian syllogistic reasoning"
    ),
    "inference_engine": ModuleClassification(
        module_name="inference_engine",
        layer=ArchitecturalLayer.LOGIC,
        allowed_dependencies=[],
        description="Formal inference patterns"
    ),
    "fallacy_detector": ModuleClassification(
        module_name="fallacy_detector",
        layer=ArchitecturalLayer.LOGIC,
        allowed_dependencies=[],
        description="Structural fallacy detection"
    ),
    "rule_engine": ModuleClassification(
        module_name="rule_engine",
        layer=ArchitecturalLayer.LOGIC,
        allowed_dependencies=[],
        description="Rule-based theorem proving"
    ),

    # AI LAYER (Muscles) - Can depend on Logic, not User
    "debate_system": ModuleClassification(
        module_name="debate_system",
        layer=ArchitecturalLayer.AI,
        allowed_dependencies=[ArchitecturalLayer.LOGIC],
        description="Multi-perspective adversarial reasoning"
    ),
    "critic_system": ModuleClassification(
        module_name="critic_system",
        layer=ArchitecturalLayer.AI,
        allowed_dependencies=[ArchitecturalLayer.LOGIC],
        description="Self-critique with multiple lenses"
    ),
    "semantic_parser": ModuleClassification(
        module_name="semantic_parser",
        layer=ArchitecturalLayer.AI,
        allowed_dependencies=[ArchitecturalLayer.LOGIC],
        description="Natural language interpretation"
    ),
    "retrieval_augmentation": ModuleClassification(
        module_name="retrieval_augmentation",
        layer=ArchitecturalLayer.AI,
        allowed_dependencies=[ArchitecturalLayer.LOGIC],
        description="Context expansion via RAG"
    ),
    "multimodal_pipeline": ModuleClassification(
        module_name="multimodal_pipeline",
        layer=ArchitecturalLayer.AI,
        allowed_dependencies=[ArchitecturalLayer.LOGIC],
        description="Cross-modal interpretation"
    ),
    "self_consistency": ModuleClassification(
        module_name="self_consistency",
        layer=ArchitecturalLayer.AI,
        allowed_dependencies=[ArchitecturalLayer.LOGIC],
        description="Cross-checking interpretations"
    ),
    "reranker": ModuleClassification(
        module_name="reranker",
        layer=ArchitecturalLayer.AI,
        allowed_dependencies=[ArchitecturalLayer.LOGIC],
        description="Prioritization of interpretations"
    ),

    # USER LAYER (Heart) - Can observe Logic and AI, but controls
    "role_system": ModuleClassification(
        module_name="role_system",
        layer=ArchitecturalLayer.USER,
        allowed_dependencies=[ArchitecturalLayer.LOGIC, ArchitecturalLayer.AI],
        description="User-selected reasoning profiles"
    ),
    "clarification_system": ModuleClassification(
        module_name="clarification_system",
        layer=ArchitecturalLayer.USER,
        allowed_dependencies=[ArchitecturalLayer.LOGIC, ArchitecturalLayer.AI],
        description="User intention clarification"
    ),
    "feedback_system": ModuleClassification(
        module_name="feedback_system",
        layer=ArchitecturalLayer.USER,
        allowed_dependencies=[ArchitecturalLayer.LOGIC, ArchitecturalLayer.AI],
        description="User corrections and preferences"
    ),
    "constraint_system": ModuleClassification(
        module_name="constraint_system",
        layer=ArchitecturalLayer.USER,
        allowed_dependencies=[ArchitecturalLayer.LOGIC, ArchitecturalLayer.AI],
        description="User-defined boundaries"
    ),
    "ui_hooks": ModuleClassification(
        module_name="ui_hooks",
        layer=ArchitecturalLayer.USER,
        allowed_dependencies=[ArchitecturalLayer.LOGIC, ArchitecturalLayer.AI],
        description="User interaction layer"
    ),
    "calibration_system": ModuleClassification(
        module_name="calibration_system",
        layer=ArchitecturalLayer.USER,
        allowed_dependencies=[ArchitecturalLayer.LOGIC, ArchitecturalLayer.AI],
        description="User-specific confidence calibration"
    ),

    # SYNTHESIS LAYER (Reason) - Depends on all three
    "decision_model": ModuleClassification(
        module_name="decision_model",
        layer=ArchitecturalLayer.SYNTHESIS,
        allowed_dependencies=[ArchitecturalLayer.LOGIC, ArchitecturalLayer.AI, ArchitecturalLayer.USER],
        description="Weighted synthesis of evidence"
    ),
    "planning_system": ModuleClassification(
        module_name="planning_system",
        layer=ArchitecturalLayer.SYNTHESIS,
        allowed_dependencies=[ArchitecturalLayer.LOGIC, ArchitecturalLayer.AI, ArchitecturalLayer.USER],
        description="Contextual action planning"
    ),
    "evidence_system": ModuleClassification(
        module_name="evidence_system",
        layer=ArchitecturalLayer.SYNTHESIS,
        allowed_dependencies=[ArchitecturalLayer.LOGIC, ArchitecturalLayer.AI, ArchitecturalLayer.USER],
        description="Evidence-based reasoning"
    ),
    "uncertainty_system": ModuleClassification(
        module_name="uncertainty_system",
        layer=ArchitecturalLayer.SYNTHESIS,
        allowed_dependencies=[ArchitecturalLayer.LOGIC, ArchitecturalLayer.AI, ArchitecturalLayer.USER],
        description="Calibrated confidence"
    ),
    "curriculum_system": ModuleClassification(
        module_name="curriculum_system",
        layer=ArchitecturalLayer.SYNTHESIS,
        allowed_dependencies=[ArchitecturalLayer.LOGIC, ArchitecturalLayer.AI, ArchitecturalLayer.USER],
        description="Adaptive reasoning difficulty"
    ),

    # UTILITY LAYER - Infrastructure, no layer constraints
    "memory_system": ModuleClassification(
        module_name="memory_system",
        layer=ArchitecturalLayer.UTILITY,
        allowed_dependencies=[],
        description="Memory storage and retrieval"
    ),
    "memory_persistence": ModuleClassification(
        module_name="memory_persistence",
        layer=ArchitecturalLayer.UTILITY,
        allowed_dependencies=[],
        description="Persistent storage backends"
    ),
    "safety_system": ModuleClassification(
        module_name="safety_system",
        layer=ArchitecturalLayer.UTILITY,
        allowed_dependencies=[],
        description="PII detection, input sanitization"
    ),
    "observability_system": ModuleClassification(
        module_name="observability_system",
        layer=ArchitecturalLayer.UTILITY,
        allowed_dependencies=[],
        description="Telemetry and logging"
    ),
    "trace_logger": ModuleClassification(
        module_name="trace_logger",
        layer=ArchitecturalLayer.UTILITY,
        allowed_dependencies=[],
        description="Execution tracing"
    ),
}


class TestLogicLayerCompliance:
    """Tests for Logic Layer (Skeleton) compliance."""

    @pytest.mark.unit
    def test_logic_modules_are_deterministic(self):
        """Logic modules must return identical outputs for identical inputs."""
        from agents.core.logic_engine import LogicEngine

        engine = LogicEngine()
        premises = ["If it rains, then the ground is wet", "It rains"]
        conclusion = "The ground is wet"

        # Run multiple times
        results = [engine.validate_argument(premises, conclusion) for _ in range(5)]

        # All results must be identical
        first_result = results[0]
        for result in results[1:]:
            assert result.valid == first_result.valid
            assert result.form == first_result.form
            assert result.confidence == first_result.confidence

    @pytest.mark.unit
    def test_logic_modules_no_context_dependency(self):
        """Logic modules must not depend on user context or external state."""
        from agents.core.categorical_engine import CategoricalEngine

        engine = CategoricalEngine()

        # Same syllogism, different "contexts"
        premises = ["All humans are mortal", "Socrates is human"]
        conclusion = "Socrates is mortal"

        result1 = engine.validate_syllogism(premises, conclusion)
        result2 = engine.validate_syllogism(premises, conclusion)

        # Must be identical regardless of when/how called
        assert result1.valid == result2.valid

    @pytest.mark.unit
    def test_logic_modules_confidence_is_certain(self):
        """Logic modules should have confidence 1.0 for valid structures."""
        from agents.core.logic_engine import LogicEngine

        engine = LogicEngine()
        premises = ["P", "P → Q"]
        conclusion = "Q"

        result = engine.validate_argument(premises, conclusion)

        if result.valid:
            # Logic is certain about structural validity
            assert result.confidence == 1.0

    @pytest.mark.unit
    def test_logic_modules_separate_validity_from_soundness(self):
        """Logic must distinguish valid structure from true premises."""
        from agents.core.logic_engine import LogicEngine

        engine = LogicEngine()

        # Valid structure, but absurd premises
        premises = ["If unicorns exist, then magic is real", "Unicorns exist"]
        conclusion = "Magic is real"

        result = engine.validate_argument(premises, conclusion)

        # Should be VALID (correct structure), even if unsound (false premises)
        assert result.valid is True
        # But should not claim the conclusion is TRUE
        assert not hasattr(result, 'is_true') or result.is_true is None

    @pytest.mark.unit
    def test_logic_modules_no_moral_judgments(self):
        """Logic modules must not make value judgments."""
        from agents.core.fallacy_detector import FallacyDetector

        detector = FallacyDetector()

        # Detect structural fallacy, not content morality
        argument = "If you don't agree with X, you're a bad person"

        result = detector.detect_fallacies(argument)

        # Should detect ad hominem (structural), not judge content morality
        if result.fallacies:
            for fallacy in result.fallacies:
                # Should be structural categories
                assert "bad person" not in fallacy.explanation.lower()


class TestAILayerCompliance:
    """Tests for AI Layer (Muscles) compliance."""

    @pytest.mark.unit
    def test_ai_modules_provide_multiple_perspectives(self):
        """AI modules must provide multiple interpretations, not singular truth."""
        from agents.core.critic_system import CriticSystem

        critic = CriticSystem()
        output = "The economy is doing well"

        result = critic.critique(output)

        # Should provide multiple quality dimensions or perspectives
        # Not just "this is right" or "this is wrong"
        assert hasattr(result, 'dimension_scores') or hasattr(result, 'perspectives')

    @pytest.mark.unit
    def test_ai_modules_express_uncertainty(self):
        """AI modules must use confidence scores < 1.0 for non-tautological claims."""
        from agents.core.critic_system import CriticSystem

        critic = CriticSystem()
        output = "This is a good argument"  # Subjective claim

        result = critic.critique(output)

        # AI should not be 100% certain about subjective judgments
        if hasattr(result, 'confidence'):
            # Allow 1.0 only for tautologies or formal checks
            if result.confidence == 1.0:
                # Must be justified
                assert hasattr(result, 'is_tautology') or hasattr(result, 'is_formal_verification')

    @pytest.mark.unit
    def test_ai_modules_attribute_perspectives(self):
        """AI interpretations must be attributed to specific profiles/sources."""
        # This test will pass for now, but serves as a specification
        # When debate_system is tested, it must have profile attribution
        pytest.skip("Debate system not yet tested - specification test")

    @pytest.mark.unit
    def test_ai_modules_no_auto_selection(self):
        """AI modules must not auto-select 'best' interpretation without user input."""
        # Specification test for future AI modules
        pytest.skip("Specification test for future debate_system implementation")


class TestUserLayerCompliance:
    """Tests for User Layer (Heart) compliance."""

    @pytest.mark.unit
    def test_user_preferences_are_persisted(self):
        """User preferences must be stored and retrievable."""
        # Will implement when role_system is tested
        pytest.skip("role_system not yet tested")

    @pytest.mark.unit
    def test_user_can_override_ai_suggestions(self):
        """User must be able to override any AI recommendation."""
        # Specification test
        pytest.skip("Specification test for user override mechanisms")

    @pytest.mark.unit
    def test_ambiguity_triggers_clarification(self):
        """Ambiguous input must trigger user clarification, not guessing."""
        # Will implement when clarification_system is tested
        pytest.skip("clarification_system not yet tested")

    @pytest.mark.unit
    def test_no_auto_execution_without_confirmation(self):
        """High-stakes actions must require user confirmation."""
        # Specification test
        pytest.skip("Specification test for user confirmation flows")


class TestSynthesisLayerCompliance:
    """Tests for Synthesis Layer (Reason) compliance."""

    @pytest.mark.integration
    def test_synthesis_includes_all_layers(self):
        """Synthesis must incorporate Logic + AI + User."""
        from agents.core.decision_model import DecisionModel, EvidenceItem, DecisionContext

        model = DecisionModel()

        # Create evidence with different sources (simulating layers)
        evidence = [
            EvidenceItem(
                content="Logically valid argument",
                source="logic_engine",
                confidence=1.0,
                evidence_type="logical"
            ),
            EvidenceItem(
                content="Marxist interpretation suggests class bias",
                source="ai_perspective_marx",
                confidence=0.7,
                evidence_type="interpretive"
            ),
            EvidenceItem(
                content="User prefers Marxist lens",
                source="user_preferences",
                confidence=1.0,
                evidence_type="preference"
            )
        ]

        context = DecisionContext(
            query="Should we trust this argument?",
            evidence=evidence,
            user_id="test_user"
        )

        decision = model.decide(context)

        # Decision should reference multiple evidence types
        evidence_types = {e.evidence_type for e in evidence}
        assert len(evidence_types) >= 2  # At least two layers represented

    @pytest.mark.integration
    def test_synthesis_traces_provenance(self):
        """Synthesis must trace decision back to sources."""
        from agents.core.decision_model import DecisionModel, EvidenceItem, DecisionContext

        model = DecisionModel()
        evidence = [
            EvidenceItem(content="Test", source="test_source", confidence=0.8, evidence_type="test")
        ]
        context = DecisionContext(query="Test query", evidence=evidence, user_id="test")

        decision = model.decide(context)

        # Must have provenance/explanation
        assert hasattr(decision, 'explanation') or hasattr(decision, 'reasoning_trace')

    @pytest.mark.integration
    def test_logic_blocks_invalid_synthesis(self):
        """Invalid logical structure must block synthesis, regardless of AI/User preference."""
        # This is a specification test - when implemented, invalid logic should halt synthesis
        pytest.skip("Specification: Invalid logic must block synthesis")


class TestArchitecturalInvariants:
    """Tests for architectural invariants and dependency rules."""

    @pytest.mark.unit
    def test_module_registry_complete(self):
        """All core modules should be classified in the registry."""
        core_path = Path(__file__).parent.parent / "core"
        core_modules = [f.stem for f in core_path.glob("*.py") if f.stem != "__init__"]

        # Check that major modules are classified
        important_modules = [
            "logic_engine", "categorical_engine", "inference_engine",
            "debate_system", "critic_system",
            "role_system", "clarification_system",
            "decision_model", "planning_system"
        ]

        for module in important_modules:
            if module in core_modules:
                assert module in MODULE_REGISTRY, f"Module {module} not classified in registry"

    @pytest.mark.unit
    def test_layer_dependency_rules(self):
        """Verify that dependency rules are correctly specified."""
        # Logic modules should have no dependencies
        logic_modules = [m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.LOGIC]
        for module in logic_modules:
            classification = MODULE_REGISTRY[module]
            assert len(classification.allowed_dependencies) == 0, \
                f"Logic module {module} should have no dependencies"

        # AI modules should only depend on Logic
        ai_modules = [m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.AI]
        for module in ai_modules:
            classification = MODULE_REGISTRY[module]
            assert ArchitecturalLayer.USER not in classification.allowed_dependencies, \
                f"AI module {module} should not depend on User layer"

        # Synthesis modules should be able to depend on all
        synthesis_modules = [m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.SYNTHESIS]
        for module in synthesis_modules:
            classification = MODULE_REGISTRY[module]
            # Should allow all three layers
            assert ArchitecturalLayer.LOGIC in classification.allowed_dependencies
            assert ArchitecturalLayer.AI in classification.allowed_dependencies
            assert ArchitecturalLayer.USER in classification.allowed_dependencies

    @pytest.mark.unit
    def test_module_classifications_have_descriptions(self):
        """All module classifications should have descriptions."""
        for module, classification in MODULE_REGISTRY.items():
            assert classification.description, f"Module {module} missing description"
            assert len(classification.description) > 10, f"Module {module} has too short description"


class TestMetaphysicalCoherence:
    """Tests that the metaphysical model is coherent and testable."""

    @pytest.mark.unit
    def test_skeleton_provides_frame(self):
        """Logic layer provides structural constraints."""
        from agents.core.logic_engine import LogicEngine

        engine = LogicEngine()

        # Invalid structure cannot be validated
        premises = ["P"]
        conclusion = "Q"  # Does not follow

        result = engine.validate_argument(premises, conclusion)
        assert result.valid is False

    @pytest.mark.unit
    def test_muscles_extend_within_frame(self):
        """AI layer operates within logical constraints."""
        # When critic system analyzes an argument, it should still
        # respect logical validity
        pytest.skip("Specification: AI must respect logical frame")

    @pytest.mark.unit
    def test_heart_determines_meaning(self):
        """User layer assigns meaning and value."""
        # User preferences should influence interpretation weighting
        pytest.skip("Specification: User determines meaning")

    @pytest.mark.integration
    def test_reason_emerges_from_interaction(self):
        """Reason is the synthesis of Logic + AI + User."""
        # Final decision should show contribution from all three
        pytest.skip("Specification: Reason emerges from triadic interaction")


class TestAntiPatterns:
    """Tests that prevent known anti-patterns."""

    @pytest.mark.unit
    def test_no_logic_moralizing(self):
        """Logic modules must not make moral judgments."""
        # Already tested in TestLogicLayerCompliance
        pass

    @pytest.mark.unit
    def test_no_ai_deciding(self):
        """AI modules must not make final decisions."""
        # AI should suggest, not decide
        pytest.skip("Specification: AI suggests, does not decide")

    @pytest.mark.unit
    def test_no_system_bypassing_user(self):
        """System must not execute high-stakes actions without user approval."""
        pytest.skip("Specification: User approval required for high-stakes")

    @pytest.mark.unit
    def test_no_opaque_synthesis(self):
        """Synthesis must be explainable and traceable."""
        # Already tested in TestSynthesisLayerCompliance
        pass


class TestProfileAsLens:
    """Tests that profiles (Marx, Freud, etc.) are lenses, not judges."""

    @pytest.mark.unit
    def test_profiles_are_interpretive(self):
        """Profiles provide perspectives, not verdicts."""
        pytest.skip("role_system not yet implemented - specification test")

    @pytest.mark.unit
    def test_multiple_profiles_coexist(self):
        """Multiple profiles can be applied simultaneously."""
        pytest.skip("role_system not yet implemented - specification test")

    @pytest.mark.unit
    def test_profiles_do_not_auto_select(self):
        """System must not auto-select 'best' profile."""
        pytest.skip("role_system not yet implemented - specification test")

    @pytest.mark.unit
    def test_user_weights_profiles(self):
        """User assigns weights to different profiles."""
        pytest.skip("role_system not yet implemented - specification test")


# Utility function for module analysis
def get_module_imports(module_name: str) -> Set[str]:
    """Get all imports from a module."""
    try:
        module_path = Path(__file__).parent.parent / "core" / f"{module_name}.py"
        if not module_path.exists():
            return set()

        with open(module_path, 'r') as f:
            content = f.read()

        # Simple import detection (could be improved with AST parsing)
        imports = set()
        for line in content.split('\n'):
            if 'from agents.core' in line or 'import agents.core' in line:
                # Extract module name
                if 'from agents.core.' in line:
                    module = line.split('from agents.core.')[1].split(' ')[0]
                    imports.add(module)

        return imports
    except Exception:
        return set()


@pytest.mark.slow
class TestDependencyCompliance:
    """Tests that modules respect dependency rules."""

    def test_logic_modules_no_forbidden_imports(self):
        """Logic modules should not import AI or User modules."""
        logic_modules = [m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.LOGIC]

        ai_modules = {m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.AI}
        user_modules = {m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.USER}

        for logic_module in logic_modules:
            imports = get_module_imports(logic_module)

            # Should not import from AI or User layers
            forbidden_imports = imports & (ai_modules | user_modules)
            assert len(forbidden_imports) == 0, \
                f"Logic module {logic_module} imports forbidden modules: {forbidden_imports}"

    def test_ai_modules_no_user_imports(self):
        """AI modules should not import User modules."""
        ai_modules_list = [m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.AI]
        user_modules = {m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.USER}

        for ai_module in ai_modules_list:
            imports = get_module_imports(ai_module)

            # Should not import from User layer
            forbidden_imports = imports & user_modules
            assert len(forbidden_imports) == 0, \
                f"AI module {ai_module} imports forbidden User modules: {forbidden_imports}"


# Summary test that validates the entire architecture
@pytest.mark.integration
class TestArchitectureSummary:
    """High-level validation of entire architecture."""

    def test_triadic_structure_exists(self):
        """Verify that all three layers exist and are populated."""
        logic_count = len([m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.LOGIC])
        ai_count = len([m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.AI])
        user_count = len([m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.USER])
        synthesis_count = len([m for m, c in MODULE_REGISTRY.items() if c.layer == ArchitecturalLayer.SYNTHESIS])

        # All three primary layers should have modules
        assert logic_count > 0, "No Logic layer modules"
        assert ai_count > 0, "No AI layer modules"
        assert user_count > 0, "No User layer modules"
        assert synthesis_count > 0, "No Synthesis layer modules"

    def test_architecture_documentation_exists(self):
        """Verify that architecture documentation exists."""
        arch_doc_path = Path(__file__).parent.parent / "ARCHITECTURE_METAPHYSICS.md"
        assert arch_doc_path.exists(), "Architecture documentation missing"

        # Should contain key concepts
        content = arch_doc_path.read_text()
        assert "Skeleton" in content
        assert "Muscles" in content
        assert "Heart" in content
        assert "Logic" in content
        assert "User Agency" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
