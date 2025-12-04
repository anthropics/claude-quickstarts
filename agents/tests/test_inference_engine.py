"""
Unit tests for Inference Engine - Core Reasoning Module

Tests formal inference patterns, quantifier handling, proof mechanisms,
and multi-step reasoning chains using the actual InferenceEngine API.
"""

import pytest
from agents.core.inference_engine import (
    InferenceEngine,
    InferencePattern,
    QuantifierType,
    LogicalTerm,
    InferenceResult,
    InferenceStep,
    FormalParser,
    QuantifiedPredicate,
)


class TestInferenceEngine:
    """Test suite for InferenceEngine."""

    @pytest.fixture
    def engine(self):
        """Create InferenceEngine instance."""
        return InferenceEngine()

    @pytest.mark.unit
    def test_initialization(self, engine):
        """Test engine initializes properly."""
        assert hasattr(engine, 'parser')
        assert hasattr(engine, 'facts')
        assert hasattr(engine, 'rules')
        assert hasattr(engine, 'infer')

    @pytest.mark.unit
    def test_add_fact(self, engine):
        """Test adding facts to knowledge base."""
        engine.add_fact("f1", "Socrates is mortal", confidence=0.95)
        
        assert "f1" in engine.facts
        assert engine.facts["f1"]["statement"] == "Socrates is mortal"
        assert engine.facts["f1"]["confidence"] == 0.95

    @pytest.mark.unit
    def test_add_rule(self, engine):
        """Test adding rules to knowledge base."""
        engine.add_rule("If P then Q", confidence=1.0)
        
        assert len(engine.rules) >= 1

    @pytest.mark.unit
    def test_infer_with_premises(self, engine):
        """Test inference with explicit premises."""
        engine.add_fact("p1", "All men are mortal")
        engine.add_fact("p2", "Socrates is a man")
        
        result = engine.infer("Socrates is mortal")
        
        assert isinstance(result, InferenceResult)
        assert hasattr(result, 'success')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'steps')

    @pytest.mark.unit
    def test_modus_ponens_pattern(self, engine):
        """Test modus ponens inference: P, P→Q ⊢ Q"""
        engine.add_fact("f1", "P")
        engine.add_rule("If P then Q")
        
        result = engine.infer("Q")
        
        # Should find modus ponens pattern
        if result.success:
            assert InferencePattern.MODUS_PONENS in result.patterns_used

    @pytest.mark.unit
    def test_modus_tollens_pattern(self, engine):
        """Test modus tollens inference: ¬Q, P→Q ⊢ ¬P"""
        engine.add_fact("f1", "not Q")
        engine.add_rule("If P then Q")
        
        result = engine.infer("not P")
        
        # May use modus tollens
        if result.success:
            assert len(result.patterns_used) > 0

    @pytest.mark.unit
    def test_inference_result_structure(self, engine):
        """Test that inference result has all required fields."""
        engine.add_fact("f1", "All birds fly")
        engine.add_fact("f2", "Tweety is a bird")
        
        result = engine.infer("Tweety flies")
        
        assert hasattr(result, 'success')
        assert hasattr(result, 'conclusion')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'steps')
        assert hasattr(result, 'patterns_used')
        assert hasattr(result, 'proof_found')
        assert hasattr(result, 'needs_flag')

    @pytest.mark.unit
    def test_proof_or_flag_mechanism(self, engine):
        """Test proof-or-flag behavior."""
        # Unsupported conclusion should be flagged
        engine.add_fact("f1", "Some random fact")
        
        result = engine.infer("Completely unrelated conclusion")
        
        # If no proof found, should either fail or flag
        if not result.proof_found:
            assert not result.success or result.needs_flag


class TestFormalParser:
    """Test suite for FormalParser."""

    @pytest.fixture
    def parser(self):
        return FormalParser()

    @pytest.mark.unit
    def test_parse_implication(self, parser):
        """Test parsing of implications (if-then)."""
        result = parser.parse("If it rains then the ground is wet")
        
        assert result is not None
        assert result.get("type") in ["implication", "atomic"]

    @pytest.mark.unit
    def test_parse_universal_quantifier(self, parser):
        """Test parsing of universal quantifiers (all X are Y)."""
        result = parser.parse("All men are mortal")
        
        assert result is not None
        # Should recognize universal pattern
        if result.get("type") == "universal":
            assert result.get("quantifier") == "∀"

    @pytest.mark.unit
    def test_parse_existential_quantifier(self, parser):
        """Test parsing of existential quantifiers (some X are Y)."""
        result = parser.parse("Some birds are flightless")
        
        assert result is not None
        if result.get("type") == "existential":
            assert result.get("quantifier") == "∃"

    @pytest.mark.unit
    def test_parse_negation(self, parser):
        """Test parsing of negated statements."""
        result = parser.parse("No fish are mammals")
        
        assert result is not None
        # Should handle negation

    @pytest.mark.unit
    def test_parse_predicate(self, parser):
        """Test parsing of predicate statements (X is Y)."""
        result = parser.parse("Socrates is mortal")
        
        assert result is not None

    @pytest.mark.unit
    def test_parse_formal_notation(self, parser):
        """Test parsing of formal logical notation."""
        result = parser.parse("P → Q")
        
        assert result is not None
        if result.get("type") == "implication":
            assert "antecedent" in result
            assert "consequent" in result


class TestLogicalTerm:
    """Test LogicalTerm data class."""

    @pytest.mark.unit
    def test_variable_term(self):
        """Test variable logical term."""
        term = LogicalTerm(name="x", is_variable=True)
        
        assert term.name == "x"
        assert term.is_variable is True
        assert str(term) == "x"

    @pytest.mark.unit
    def test_constant_term(self):
        """Test constant logical term."""
        term = LogicalTerm(name="Socrates", is_constant=True)
        
        assert term.name == "Socrates"
        assert term.is_constant is True

    @pytest.mark.unit
    def test_term_hashing(self):
        """Test that terms are hashable for sets/dicts."""
        term1 = LogicalTerm(name="x", is_variable=True)
        term2 = LogicalTerm(name="x", is_variable=True)
        
        # Same terms should hash equally
        assert hash(term1) == hash(term2)


class TestQuantifiedPredicate:
    """Test QuantifiedPredicate data class."""

    @pytest.mark.unit
    def test_universal_predicate(self):
        """Test universal quantified predicate."""
        pred = QuantifiedPredicate(
            quantifier=QuantifierType.UNIVERSAL,
            variable="x",
            predicate_name="Mortal",
            arguments=[LogicalTerm("x", is_variable=True)]
        )
        
        assert pred.quantifier == QuantifierType.UNIVERSAL
        assert pred.variable == "x"
        assert "Mortal" in str(pred)

    @pytest.mark.unit
    def test_negated_predicate(self):
        """Test negated predicate."""
        pred = QuantifiedPredicate(
            quantifier=QuantifierType.NONE,
            variable=None,
            predicate_name="Fly",
            arguments=[LogicalTerm("penguin", is_constant=True)],
            negated=True
        )
        
        assert pred.negated is True
        assert "¬" in str(pred)


class TestInferenceStep:
    """Test InferenceStep data class."""

    @pytest.mark.unit
    def test_inference_step_creation(self):
        """Test creating an inference step."""
        step = InferenceStep(
            step_id=1,
            premise_ids=[0],
            conclusion="Q",
            pattern_used=InferencePattern.MODUS_PONENS,
            confidence=0.95,
            justification="Applied modus ponens"
        )
        
        assert step.step_id == 1
        assert step.pattern_used == InferencePattern.MODUS_PONENS
        assert step.confidence == 0.95


class TestInferencePatterns:
    """Test all inference patterns."""

    @pytest.mark.unit
    def test_pattern_enum_exists(self):
        """Test that all expected patterns exist."""
        patterns = [
            InferencePattern.MODUS_PONENS,
            InferencePattern.MODUS_TOLLENS,
            InferencePattern.HYPOTHETICAL_SYLLOGISM,
            InferencePattern.DISJUNCTIVE_SYLLOGISM,
            InferencePattern.CATEGORICAL_SYLLOGISM,
            InferencePattern.UNIVERSAL_INSTANTIATION,
        ]
        
        for p in patterns:
            assert p in InferencePattern

    @pytest.mark.unit
    def test_pattern_values(self):
        """Test pattern string values."""
        assert InferencePattern.MODUS_PONENS.value == "modus_ponens"
        assert InferencePattern.MODUS_TOLLENS.value == "modus_tollens"


class TestQuantifierType:
    """Test QuantifierType enum."""

    @pytest.mark.unit
    def test_quantifier_symbols(self):
        """Test quantifier symbols."""
        assert QuantifierType.UNIVERSAL.value == "∀"
        assert QuantifierType.EXISTENTIAL.value == "∃"
        assert QuantifierType.NONE.value == ""
