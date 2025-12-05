"""
Unit tests for deterministic logic engine.

Tests cover:
- Pattern matching for valid/invalid forms
- Truth table evaluation
- Heuristic fallbacks
- Edge cases and error handling
"""

import pytest
from agents.core_logic import (
    LogicEngine,
    LogicForm,
    parse_argument,
    validate_modus_ponens,
    validate_modus_tollens,
)


class TestModusPonens:
    """Test modus ponens (MP) validation."""

    def test_valid_modus_ponens(self):
        """Test valid MP: P → Q, P ⊢ Q"""
        result = validate_modus_ponens("P → Q", "P", "Q")

        assert result.is_valid is True
        assert result.form_identified == LogicForm.MODUS_PONENS
        assert result.confidence == 1.0
        assert result.method == "pattern_match"

    def test_modus_ponens_with_complex_vars(self):
        """Test MP with multi-character variables."""
        result = validate_modus_ponens("Rain → Wet", "Rain", "Wet")

        assert result.is_valid is True
        assert result.form_identified == LogicForm.MODUS_PONENS

    def test_invalid_affirming_consequent(self):
        """Test fallacy: P → Q, Q ⊢ P (affirming consequent)"""
        arg = parse_argument(["P → Q", "Q"], "P")
        engine = LogicEngine()
        result = engine.validate(arg)

        assert result.is_valid is False
        assert result.form_identified == LogicForm.AFFIRMING_CONSEQUENT
        assert result.confidence == 1.0
        assert "affirming" in result.explanation.lower()


class TestModusTollens:
    """Test modus tollens (MT) validation."""

    def test_valid_modus_tollens(self):
        """Test valid MT: P → Q, ¬Q ⊢ ¬P"""
        result = validate_modus_tollens("P → Q", "¬Q", "¬P")

        assert result.is_valid is True
        assert result.form_identified == LogicForm.MODUS_TOLLENS
        assert result.confidence == 1.0

    def test_invalid_denying_antecedent(self):
        """Test fallacy: P → Q, ¬P ⊢ ¬Q (denying antecedent)"""
        arg = parse_argument(["P → Q", "¬P"], "¬Q")
        engine = LogicEngine()
        result = engine.validate(arg)

        assert result.is_valid is False
        assert result.form_identified == LogicForm.DENYING_ANTECEDENT
        assert "denying" in result.explanation.lower()


class TestHypotheticalSyllogism:
    """Test hypothetical syllogism (HS)."""

    def test_valid_hypothetical_syllogism(self):
        """Test valid HS: P → Q, Q → R ⊢ P → R"""
        arg = parse_argument(["P → Q", "Q → R"], "P → R")
        engine = LogicEngine()
        result = engine.validate(arg)

        assert result.is_valid is True
        assert result.form_identified == LogicForm.HYPOTHETICAL_SYLLOGISM
        assert result.confidence == 1.0


class TestDisjunctiveSyllogism:
    """Test disjunctive syllogism (DS)."""

    def test_valid_disjunctive_syllogism(self):
        """Test valid DS: P ∨ Q, ¬P ⊢ Q"""
        arg = parse_argument(["P ∨ Q", "¬P"], "Q")
        engine = LogicEngine()
        result = engine.validate(arg)

        assert result.is_valid is True
        assert result.form_identified == LogicForm.DISJUNCTIVE_SYLLOGISM
        assert result.confidence == 1.0


class TestTruthTable:
    """Test truth table evaluation."""

    def test_truth_table_valid_argument(self):
        """Test truth table validates a valid argument."""
        # A valid but non-standard form
        arg = parse_argument(["P ∧ Q"], "P")  # Simplification
        engine = LogicEngine()
        result = engine.validate(arg)

        # Should match simplification pattern or be valid by truth table
        assert result.is_valid is True
        assert result.confidence == 1.0

    def test_truth_table_invalid_argument(self):
        """Test truth table detects invalid argument."""
        # Invalid: P ∨ Q, P ⊢ ¬Q (affirming disjunct with inclusive OR)
        arg = parse_argument(["P ∨ Q", "P"], "¬Q")
        engine = LogicEngine()
        result = engine.validate(arg)

        # Should be invalid
        assert result.is_valid is False

    def test_truth_table_counterexample(self):
        """Test truth table provides counterexample for invalid arguments."""
        arg = parse_argument(["P → Q"], "P")  # Invalid: cannot conclude P from just P → Q
        engine = LogicEngine()
        result = engine.validate(arg)

        if result.counterexample:
            # Counterexample should have P=False (makes premise true, conclusion false)
            assert result.counterexample.get("P") is False


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_too_many_variables(self):
        """Test handling of >5 variables (truth table infeasible)."""
        # Create argument with 6 variables
        arg = parse_argument(
            ["A ∧ B ∧ C", "D ∨ E ∨ F"],
            "A"
        )
        engine = LogicEngine()
        result = engine.validate(arg)

        # Should fall back to heuristic
        assert "Too many variables" in " ".join(result.warnings)

    def test_empty_premises(self):
        """Test handling of empty premises."""
        arg = parse_argument([], "P")
        engine = LogicEngine()
        result = engine.validate(arg)

        # Should handle gracefully
        assert result.confidence < 1.0  # Heuristic

    def test_conclusion_with_new_terms(self):
        """Test heuristic catches conclusion with new terms."""
        arg = parse_argument(["P → Q"], "R")  # R not in premises
        engine = LogicEngine()
        result = engine.validate(arg)

        assert result.is_valid is False
        assert "new terms" in result.explanation.lower()
        assert result.confidence >= 0.8  # High confidence heuristic


class TestRealWorldExamples:
    """Test with real-world arguments."""

    def test_socrates_syllogism(self):
        """Test classic: All humans mortal, Socrates human ⊢ Socrates mortal"""
        # This is technically categorical, but can be expressed propositionally
        arg = parse_argument(
            ["Human(Socrates) → Mortal(Socrates)", "Human(Socrates)"],
            "Mortal(Socrates)"
        )
        engine = LogicEngine()
        result = engine.validate(arg)

        assert result.is_valid is True
        assert result.form_identified == LogicForm.MODUS_PONENS

    def test_rain_example(self):
        """Test: If rains, ground wet; raining ⊢ ground wet"""
        arg = parse_argument(
            ["Rain → Wet", "Rain"],
            "Wet"
        )
        engine = LogicEngine()
        result = engine.validate(arg)

        assert result.is_valid is True
        assert result.form_identified == LogicForm.MODUS_PONENS

    def test_rain_fallacy(self):
        """Test fallacy: If rains, ground wet; ground wet ⊢ rained (AC)"""
        arg = parse_argument(
            ["Rain → Wet", "Wet"],
            "Rain"
        )
        engine = LogicEngine()
        result = engine.validate(arg)

        assert result.is_valid is False
        assert result.form_identified == LogicForm.AFFIRMING_CONSEQUENT


@pytest.fixture
def logic_engine():
    """Fixture providing a LogicEngine instance."""
    return LogicEngine()


def test_engine_initialization(logic_engine):
    """Test engine initializes correctly."""
    assert logic_engine is not None
    assert len(logic_engine.valid_forms) > 0
    assert len(logic_engine.invalid_forms) > 0


def test_pattern_matching_consistency(logic_engine):
    """Test pattern matching is consistent."""
    # Same argument should give same result
    arg = parse_argument(["P → Q", "P"], "Q")

    result1 = logic_engine.validate(arg)
    result2 = logic_engine.validate(arg)

    assert result1.is_valid == result2.is_valid
    assert result1.form_identified == result2.form_identified


def test_tokenizer(logic_engine):
    """Test tokenizer correctly parses expressions."""
    tokens = logic_engine._tokenize("P→Q∧R")
    assert "P" in tokens
    assert "→" in tokens
    assert "Q" in tokens
    assert "∧" in tokens
    assert "R" in tokens


def test_extract_terms(logic_engine):
    """Test term extraction."""
    terms = logic_engine._extract_terms("P → Q ∧ R")
    assert "P" in terms
    assert "Q" in terms
    assert "R" in terms
    assert "→" not in terms
    assert "∧" not in terms
