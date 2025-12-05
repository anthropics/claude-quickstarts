"""
Unit tests for categorical (syllogistic) logic engine.

Tests cover:
- Valid syllogistic forms (Barbara, Celarent, Darii, Ferio, etc.)
- Invalid forms (undistributed middle, illicit major/minor)
- Rule validation
- Parsing of categorical statements
"""

import pytest
from agents.core_logic import (
    CategoricalEngine,
    StatementType,
    Figure,
    parse_categorical_statement,
    parse_syllogism,
    validate_barbara,
)


class TestBarbaraForm:
    """Test Barbara (AAA-1): All M are P, All S are M ⊢ All S are P"""

    def test_valid_barbara(self):
        """Test valid Barbara syllogism."""
        result = validate_barbara(
            "All mammals are animals",
            "All dogs are mammals",
            "All dogs are animals"
        )

        assert result.is_valid is True
        assert result.form_name == "Barbara"
        assert result.mood == "AAA"
        assert result.figure == Figure.FIRST
        assert result.confidence == 1.0
        assert len(result.violations) == 0

    def test_barbara_with_different_content(self):
        """Test Barbara with different subject matter."""
        result = validate_barbara(
            "All planets orbit stars",
            "All jupiters are planets",
            "All jupiters orbit stars"
        )

        assert result.is_valid is True
        assert result.form_name == "Barbara"


class TestCelarent:
    """Test Celarent (EAE-1): No M are P, All S are M ⊢ No S are P"""

    def test_valid_celarent(self):
        """Test valid Celarent syllogism."""
        syl = parse_syllogism(
            "No mammals are reptiles",
            "All dogs are mammals",
            "No dogs are reptiles"
        )

        engine = CategoricalEngine()
        result = engine.validate(syl)

        assert result.is_valid is True
        assert result.form_name == "Celarent"
        assert result.mood == "EAE"
        assert result.figure == Figure.FIRST


class TestDarii:
    """Test Darii (AII-1): All M are P, Some S are M ⊢ Some S are P"""

    def test_valid_darii(self):
        """Test valid Darii syllogism."""
        syl = parse_syllogism(
            "All mammals are animals",
            "Some pets are mammals",
            "Some pets are animals"
        )

        engine = CategoricalEngine()
        result = engine.validate(syl)

        assert result.is_valid is True
        assert result.form_name == "Darii"
        assert result.mood == "AII"


class TestFerio:
    """Test Ferio (EIO-1): No M are P, Some S are M ⊢ Some S are not P"""

    def test_valid_ferio(self):
        """Test valid Ferio syllogism."""
        syl = parse_syllogism(
            "No reptiles are mammals",
            "Some pets are reptiles",
            "Some pets are not mammals"
        )

        engine = CategoricalEngine()
        result = engine.validate(syl)

        assert result.is_valid is True
        assert result.form_name == "Ferio"
        assert result.mood == "EIO"


class TestInvalidForms:
    """Test detection of invalid syllogisms."""

    def test_undistributed_middle(self):
        """Test detection of undistributed middle fallacy."""
        # All dogs are mammals, All cats are mammals ⊢ All dogs are cats (INVALID)
        syl = parse_syllogism(
            "All dogs are mammals",
            "All cats are mammals",
            "All dogs are cats"
        )

        engine = CategoricalEngine()
        result = engine.validate(syl)

        assert result.is_valid is False
        assert any("undistributed middle" in v.lower() for v in result.violations)

    def test_illicit_major(self):
        """Test detection of illicit major fallacy."""
        # All dogs are animals, No cats are dogs ⊢ No cats are animals (INVALID)
        syl = parse_syllogism(
            "All dogs are animals",
            "No cats are dogs",
            "No cats are animals"
        )

        engine = CategoricalEngine()
        result = engine.validate(syl)

        assert result.is_valid is False
        assert any("illicit major" in v.lower() for v in result.violations)

    def test_illicit_minor(self):
        """Test detection of illicit minor fallacy."""
        # All mammals are animals, All mammals are warm-blooded
        # ⊢ All warm-blooded are animals (INVALID)
        syl = parse_syllogism(
            "All mammals are animals",
            "All mammals are warm-blooded",
            "All warm-blooded creatures are animals"
        )

        engine = CategoricalEngine()
        result = engine.validate(syl)

        assert result.is_valid is False
        assert any("illicit minor" in v.lower() for v in result.violations)

    def test_two_negative_premises(self):
        """Test rule: two negative premises yield no conclusion."""
        syl = parse_syllogism(
            "No dogs are cats",
            "No cats are birds",
            "No dogs are birds"
        )

        engine = CategoricalEngine()
        result = engine.validate(syl)

        assert result.is_valid is False
        assert any("two negative" in v.lower() for v in result.violations)

    def test_two_particular_premises(self):
        """Test rule: two particular premises yield no conclusion."""
        syl = parse_syllogism(
            "Some dogs are pets",
            "Some pets are cats",
            "Some dogs are cats"
        )

        engine = CategoricalEngine()
        result = engine.validate(syl)

        assert result.is_valid is False
        assert any("two particular" in v.lower() for v in result.violations)


class TestStatementParsing:
    """Test parsing of categorical statements."""

    def test_parse_universal_affirmative(self):
        """Test parsing A statement: All S are P"""
        stmt = parse_categorical_statement("All dogs are mammals")

        assert stmt is not None
        assert stmt.type == StatementType.UNIVERSAL_AFFIRMATIVE
        assert stmt.subject == "dogs"
        assert stmt.predicate == "mammals"
        assert stmt.quantifier == "all"

    def test_parse_universal_negative(self):
        """Test parsing E statement: No S are P"""
        stmt = parse_categorical_statement("No dogs are cats")

        assert stmt is not None
        assert stmt.type == StatementType.UNIVERSAL_NEGATIVE
        assert stmt.subject == "dogs"
        assert stmt.predicate == "cats"
        assert stmt.quantifier == "no"

    def test_parse_particular_affirmative(self):
        """Test parsing I statement: Some S are P"""
        stmt = parse_categorical_statement("Some dogs are pets")

        assert stmt is not None
        assert stmt.type == StatementType.PARTICULAR_AFFIRMATIVE
        assert stmt.subject == "dogs"
        assert stmt.predicate == "pets"
        assert stmt.quantifier == "some"

    def test_parse_particular_negative(self):
        """Test parsing O statement: Some S are not P"""
        stmt = parse_categorical_statement("Some dogs are not pets")

        assert stmt is not None
        assert stmt.type == StatementType.PARTICULAR_NEGATIVE
        assert stmt.subject == "dogs"
        assert stmt.predicate == "pets"
        assert stmt.quantifier == "some"
        assert stmt.copula == "are not"


class TestDistribution:
    """Test distribution rules."""

    def test_universal_affirmative_distribution(self):
        """Test A: All S are P - S distributed, P not distributed"""
        stmt = parse_categorical_statement("All dogs are mammals")

        assert stmt.subject_distributed is True
        assert stmt.predicate_distributed is False

    def test_universal_negative_distribution(self):
        """Test E: No S are P - both S and P distributed"""
        stmt = parse_categorical_statement("No dogs are cats")

        assert stmt.subject_distributed is True
        assert stmt.predicate_distributed is True

    def test_particular_affirmative_distribution(self):
        """Test I: Some S are P - neither distributed"""
        stmt = parse_categorical_statement("Some dogs are pets")

        assert stmt.subject_distributed is False
        assert stmt.predicate_distributed is False

    def test_particular_negative_distribution(self):
        """Test O: Some S are not P - P distributed, S not"""
        stmt = parse_categorical_statement("Some dogs are not pets")

        assert stmt.subject_distributed is False
        assert stmt.predicate_distributed is True


class TestFigureIdentification:
    """Test identification of syllogistic figures."""

    def test_first_figure(self):
        """Test Figure 1: M-P, S-M"""
        syl = parse_syllogism(
            "All mammals are animals",  # M-P
            "All dogs are mammals",      # S-M
            "All dogs are animals"
        )

        assert syl.figure == Figure.FIRST

    def test_second_figure(self):
        """Test Figure 2: P-M, S-M"""
        # Requires specific term arrangement
        # Example: All animals are living, All dogs are living
        # Actually this is tricky - need proper second figure example
        pass  # TODO: Add proper figure 2-4 tests


class TestRealWorldSyllogisms:
    """Test with real-world examples."""

    def test_mortality_syllogism(self):
        """Test: All humans mortal, Socrates human ⊢ Socrates mortal"""
        # Note: Using "all" even for singular (standard categorical form)
        result = validate_barbara(
            "All humans are mortal",
            "All socrates are humans",  # Treating Socrates as a class
            "All socrates are mortal"
        )

        assert result.is_valid is True
        assert result.form_name == "Barbara"

    def test_animal_classification(self):
        """Test biological classification syllogism."""
        result = validate_barbara(
            "All vertebrates have spines",
            "All mammals are vertebrates",
            "All mammals have spines"
        )

        assert result.is_valid is True


@pytest.fixture
def categorical_engine():
    """Fixture providing CategoricalEngine instance."""
    return CategoricalEngine()


def test_engine_initialization(categorical_engine):
    """Test engine initializes correctly."""
    assert categorical_engine is not None
    assert len(CategoricalEngine.VALID_FORMS) > 0


def test_mood_calculation():
    """Test mood string correctly calculated."""
    syl = parse_syllogism(
        "All mammals are animals",
        "All dogs are mammals",
        "All dogs are animals"
    )

    assert syl.mood == "AAA"


def test_term_identification():
    """Test correct identification of major, minor, middle terms."""
    syl = parse_syllogism(
        "All mammals are animals",
        "All dogs are mammals",
        "All dogs are animals"
    )

    assert syl.major_term == "animals"  # Predicate of conclusion
    assert syl.minor_term == "dogs"  # Subject of conclusion
    assert syl.middle_term == "mammals"  # In premises but not conclusion
