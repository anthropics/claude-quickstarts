"""
Unit tests for Logic Orchestrator.

Tests the single entry point for deterministic reasoning,
including routing, result aggregation, and fallacy detection.
"""

import pytest
from agents.core.logic_orchestrator import (
    LogicOrchestrator,
    StructuredArgument,
    LogicAnalysisResult,
    ArgumentType,
    create_orchestrator,
    analyze_argument,
)


class TestStructuredArgument:
    """Tests for StructuredArgument data structure."""

    def test_valid_argument_creation(self):
        """Test creating a valid structured argument."""
        arg = StructuredArgument(
            premises=["All mammals are animals", "All dogs are mammals"],
            conclusion="All dogs are animals",
            argument_type=ArgumentType.CATEGORICAL
        )
        
        assert len(arg.premises) == 2
        assert arg.conclusion == "All dogs are animals"
        assert arg.argument_type == ArgumentType.CATEGORICAL

    def test_argument_requires_premises(self):
        """Test that argument must have at least one premise."""
        with pytest.raises(ValueError, match="at least one premise"):
            StructuredArgument(
                premises=[],
                conclusion="Some conclusion"
            )

    def test_argument_requires_conclusion(self):
        """Test that argument must have a conclusion."""
        with pytest.raises(ValueError, match="must have a conclusion"):
            StructuredArgument(
                premises=["Some premise"],
                conclusion=""
            )

    def test_default_argument_type_is_unknown(self):
        """Test that default argument type is UNKNOWN."""
        arg = StructuredArgument(
            premises=["P implies Q", "P"],
            conclusion="Q"
        )
        assert arg.argument_type == ArgumentType.UNKNOWN


class TestLogicAnalysisResult:
    """Tests for LogicAnalysisResult data structure."""

    def test_default_result_values(self):
        """Test default values for result."""
        result = LogicAnalysisResult()
        
        assert result.is_valid is None
        assert result.engine_used == "unknown"
        assert result.syllogism_form is None
        assert result.inference_pattern is None
        assert result.fallacies == []
        assert result.violations == []
        assert result.proof_steps is None
        assert result.confidence == 0.0
        assert result.notes == []

    def test_has_fallacies_property(self):
        """Test has_fallacies property."""
        result = LogicAnalysisResult()
        assert result.has_fallacies is False
        
        # Add a mock fallacy - would need actual FallacyPattern
        # For now just test empty case

    def test_is_sound_property(self):
        """Test is_sound property."""
        result = LogicAnalysisResult(is_valid=True)
        assert result.is_sound is True
        
        result_invalid = LogicAnalysisResult(is_valid=False)
        assert result_invalid.is_sound is False
        
        result_unknown = LogicAnalysisResult(is_valid=None)
        assert result_unknown.is_sound is None

    def test_to_dict_serialization(self):
        """Test to_dict produces valid dictionary."""
        result = LogicAnalysisResult(
            is_valid=True,
            engine_used="categorical",
            confidence=0.85,
            notes=["Test note"]
        )
        
        d = result.to_dict()
        
        assert d["is_valid"] is True
        assert d["engine_used"] == "categorical"
        assert d["confidence"] == 0.85
        assert "Test note" in d["notes"]


class TestLogicOrchestrator:
    """Tests for LogicOrchestrator class."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance."""
        return LogicOrchestrator()

    def test_initialization(self, orchestrator):
        """Test orchestrator initializes with all engines."""
        assert hasattr(orchestrator, '_categorical_engine')
        assert hasattr(orchestrator, '_inference_engine')
        assert hasattr(orchestrator, '_fallacy_detector')

    def test_analyze_categorical_argument(self, orchestrator):
        """Test analyzing a categorical argument."""
        arg = StructuredArgument(
            premises=["All mammals are animals", "All dogs are mammals"],
            conclusion="All dogs are animals",
            argument_type=ArgumentType.CATEGORICAL
        )
        
        result = orchestrator.analyze(arg)
        
        assert isinstance(result, LogicAnalysisResult)
        assert result.engine_used == "categorical"
        assert "CategoricalEngine" in str(result.notes)

    def test_analyze_propositional_argument(self, orchestrator):
        """Test analyzing a propositional argument."""
        arg = StructuredArgument(
            premises=["If it rains then ground is wet", "It rains"],
            conclusion="Ground is wet",
            argument_type=ArgumentType.PROPOSITIONAL
        )
        
        result = orchestrator.analyze(arg)
        
        assert isinstance(result, LogicAnalysisResult)
        assert result.engine_used == "propositional"
        assert "InferenceEngine" in str(result.notes)

    def test_analyze_unknown_type_uses_heuristics(self, orchestrator):
        """Test that unknown type attempts classification."""
        arg = StructuredArgument(
            premises=["All birds can fly", "Penguins are birds"],
            conclusion="Penguins can fly"
        )
        
        result = orchestrator.analyze(arg)
        
        assert isinstance(result, LogicAnalysisResult)
        # Should attempt classification
        assert any("classification" in note.lower() or "heuristic" in note.lower() 
                   for note in result.notes)

    def test_analyze_text_returns_not_implemented(self, orchestrator):
        """Test that analyze_text returns proper stub response."""
        result = orchestrator.analyze_text("This is a logical argument.")
        
        assert result.is_valid is None
        assert result.engine_used == "unknown"
        assert "not yet implemented" in str(result.notes).lower()
        assert "PARSE_NOT_IMPLEMENTED" in result.violations

    def test_check_validity_returns_tuple(self, orchestrator):
        """Test check_validity convenience method."""
        is_valid, confidence = orchestrator.check_validity(
            premises=["All A are B", "All B are C"],
            conclusion="All A are C",
            argument_type=ArgumentType.CATEGORICAL
        )
        
        assert isinstance(is_valid, bool)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_detect_fallacies_only(self, orchestrator):
        """Test fallacy-only detection."""
        text = "You can't trust his argument because he's a fool."
        
        fallacies = orchestrator.detect_fallacies_only(text)
        
        assert isinstance(fallacies, list)
        # Should detect ad hominem or similar
        # Exact result depends on fallacy_detector implementation

    def test_fallacy_detection_runs_on_all_arguments(self, orchestrator):
        """Test that fallacy detection runs regardless of argument type."""
        # Argument with potential fallacy
        arg = StructuredArgument(
            premises=["Everyone believes this is true"],
            conclusion="Therefore it must be true",
            argument_type=ArgumentType.PROPOSITIONAL
        )
        
        result = orchestrator.analyze(arg)
        
        # Fallacy detection should have run
        # (may or may not find fallacies depending on patterns)
        assert isinstance(result.fallacies, list)


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_orchestrator(self):
        """Test factory function creates orchestrator."""
        orchestrator = create_orchestrator()
        
        assert isinstance(orchestrator, LogicOrchestrator)

    def test_analyze_argument_convenience_function(self):
        """Test convenience function for one-off analysis."""
        result = analyze_argument(
            premises=["If P then Q", "P"],
            conclusion="Q",
            argument_type="propositional"
        )
        
        assert isinstance(result, LogicAnalysisResult)

    def test_analyze_argument_handles_invalid_type(self):
        """Test convenience function with invalid type string."""
        result = analyze_argument(
            premises=["Some premise"],
            conclusion="Some conclusion",
            argument_type="invalid_type"
        )
        
        assert isinstance(result, LogicAnalysisResult)
        # Should default to unknown type


class TestArgumentTypeEnum:
    """Tests for ArgumentType enum."""

    def test_all_types_defined(self):
        """Test all expected argument types exist."""
        assert ArgumentType.CATEGORICAL.value == "categorical"
        assert ArgumentType.PROPOSITIONAL.value == "propositional"
        assert ArgumentType.MIXED.value == "mixed"
        assert ArgumentType.UNKNOWN.value == "unknown"
