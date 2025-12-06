"""
Unit tests for LogicEngine - Propositional Logic Validation

Tests valid and invalid argument forms with deterministic verification.
"""

import pytest
from agents.core.logic_engine import LogicEngine, ArgumentForm, LogicResult


class TestLogicEngine:
    """Test suite for LogicEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create LogicEngine instance."""
        return LogicEngine()
    
    def test_initialization(self, engine):
        """Test engine initializes with correct forms."""
        assert len(engine.valid_forms) == 8
        assert len(engine.invalid_forms) == 2
        assert ArgumentForm.MODUS_PONENS in engine.valid_forms
        assert ArgumentForm.AFFIRMING_CONSEQUENT in engine.invalid_forms
    
    def test_modus_ponens_valid(self, engine):
        """Test valid Modus Ponens detection."""
        premises = [
            "If it rains, then the ground is wet",
            "It rains"
        ]
        conclusion = "The ground is wet"
        
        result = engine.validate_argument(premises, conclusion)
        
        assert result.valid is True
        assert result.form == ArgumentForm.MODUS_PONENS
        assert result.confidence == 1.0
        assert "Modus Ponens" in result.explanation
    
    def test_modus_tollens_valid(self, engine):
        """Test valid Modus Tollens detection."""
        premises = [
            "If it rains, then the ground is wet",
            "The ground is not wet"
        ]
        conclusion = "It does not rain"
        
        result = engine.validate_argument(premises, conclusion)
        
        assert result.valid is True
        assert result.form == ArgumentForm.MODUS_TOLLENS
        assert result.confidence == 1.0
        assert "Modus Tollens" in result.explanation
    
    def test_hypothetical_syllogism_valid(self, engine):
        """Test valid Hypothetical Syllogism detection."""
        premises = [
            "If it rains, then the ground is wet",
            "If the ground is wet, then plants grow"
        ]
        conclusion = "If it rains, then plants grow"
        
        result = engine.validate_argument(premises, conclusion)
        
        assert result.valid is True
        assert result.form == ArgumentForm.HYPOTHETICAL_SYLLOGISM
        assert result.confidence == 1.0
    
    def test_disjunctive_syllogism_valid(self, engine):
        """Test valid Disjunctive Syllogism detection."""
        premises = [
            "Either it's raining or it's snowing",
            "It's not raining"
        ]
        conclusion = "It's snowing"
        
        result = engine.validate_argument(premises, conclusion)
        
        assert result.valid is True
        assert result.form == ArgumentForm.DISJUNCTIVE_SYLLOGISM
    
    def test_indeterminate_argument(self, engine):
        """Test handling of indeterminate arguments."""
        premises = ["The sky is blue"]
        conclusion = "Water is wet"
        
        result = engine.validate_argument(premises, conclusion)
        
        assert result.valid is False
        assert result.form is None
        assert result.confidence == 0.0
        assert "Cannot determine" in result.explanation
    
    def test_list_valid_forms(self, engine):
        """Test listing all valid forms."""
        forms = engine.list_valid_forms()
        
        assert ArgumentForm.MODUS_PONENS in forms
        assert ArgumentForm.MODUS_TOLLENS in forms
        assert len(forms) == 8
    
    def test_list_invalid_forms(self, engine):
        """Test listing all invalid forms."""
        forms = engine.list_invalid_forms()
        
        assert ArgumentForm.AFFIRMING_CONSEQUENT in forms
        assert ArgumentForm.DENYING_ANTECEDENT in forms
        assert len(forms) == 2
    
    def test_get_form_description(self, engine):
        """Test getting form descriptions."""
        desc = engine.get_form_description(ArgumentForm.MODUS_PONENS)
        
        assert "If P then Q" in desc
        assert desc != "Unknown form"
    
    def test_empty_premises(self, engine):
        """Test handling of empty premises."""
        result = engine.validate_argument([], "Conclusion")
        
        assert result.valid is False
        assert result.confidence == 0.0
    
    def test_confidence_deterministic(self, engine):
        """Test that valid results always have 100% confidence."""
        premises = [
            "If all software engineers write code, then Alice writes code",
            "All software engineers write code"
        ]
        conclusion = "Alice writes code"
        
        result = engine.validate_argument(premises, conclusion)
        
        assert result.valid is True
        assert result.confidence == 1.0  # Deterministic


class TestLogicResult:
    """Test LogicResult dataclass."""
    
    def test_result_creation(self):
        """Test creating LogicResult."""
        result = LogicResult(
            valid=True,
            form=ArgumentForm.MODUS_PONENS,
            explanation="Test explanation"
        )
        
        assert result.valid is True
        assert result.form == ArgumentForm.MODUS_PONENS
        assert result.confidence == 1.0  # Default
    
    def test_result_with_custom_confidence(self):
        """Test LogicResult with custom confidence."""
        result = LogicResult(
            valid=False,
            form=None,
            explanation="Uncertain",
            confidence=0.5
        )
        
        assert result.confidence == 0.5


class TestArgumentForm:
    """Test ArgumentForm enum."""
    
    def test_valid_forms_exist(self):
        """Test all expected valid forms exist."""
        expected_valid = [
            ArgumentForm.MODUS_PONENS,
            ArgumentForm.MODUS_TOLLENS,
            ArgumentForm.HYPOTHETICAL_SYLLOGISM,
            ArgumentForm.DISJUNCTIVE_SYLLOGISM,
            ArgumentForm.CONSTRUCTIVE_DILEMMA,
            ArgumentForm.SIMPLIFICATION,
            ArgumentForm.CONJUNCTION,
            ArgumentForm.ADDITION,
        ]
        
        for form in expected_valid:
            assert isinstance(form, ArgumentForm)
    
    def test_invalid_forms_exist(self):
        """Test all expected invalid forms exist."""
        expected_invalid = [
            ArgumentForm.AFFIRMING_CONSEQUENT,
            ArgumentForm.DENYING_ANTECEDENT,
        ]
        
        for form in expected_invalid:
            assert isinstance(form, ArgumentForm)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
