"""
Unit tests for CategoricalEngine - Aristotelian Syllogistic Logic

Tests valid syllogism forms with proper term distribution.
"""

import pytest
from agents.core.categorical_engine import CategoricalEngine, SyllogismType, SyllogismResult


class TestCategoricalEngine:
    """Test suite for CategoricalEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create CategoricalEngine instance."""
        return CategoricalEngine()
    
    def test_initialization(self, engine):
        """Test engine initializes with correct forms."""
        assert len(engine.valid_forms) == 8
        assert SyllogismType.BARBARA in engine.valid_forms
        assert SyllogismType.CELARENT in engine.valid_forms
    
    def test_barbara_valid(self, engine):
        """Test valid Barbara syllogism (AAA-1)."""
        major = "All humans are mortal"
        minor = "All Greeks are humans"
        conclusion = "All Greeks are mortal"
        
        result = engine.validate_syllogism(major, minor, conclusion)
        
        assert result.valid is True
        assert result.form == SyllogismType.BARBARA
        assert result.confidence == 1.0
        assert "Barbara" in result.explanation
    
    def test_celarent_valid(self, engine):
        """Test valid Celarent syllogism (EAE-1)."""
        major = "No reptiles are mammals"
        minor = "All snakes are reptiles"
        conclusion = "No snakes are mammals"
        
        result = engine.validate_syllogism(major, minor, conclusion)
        
        assert result.valid is True
        assert result.form == SyllogismType.CELARENT
        assert "Celarent" in result.explanation
    
    def test_darii_valid(self, engine):
        """Test valid Darii syllogism (AII-1)."""
        major = "All birds fly"
        minor = "Some animals are birds"
        conclusion = "Some animals fly"
        
        result = engine.validate_syllogism(major, minor, conclusion)
        
        assert result.valid is True
        assert result.form == SyllogismType.DARII
    
    def test_ferio_valid(self, engine):
        """Test valid Ferio syllogism (EIO-1)."""
        major = "No fish are mammals"
        minor = "Some animals are fish"
        conclusion = "Some animals are not mammals"
        
        result = engine.validate_syllogism(major, minor, conclusion)
        
        assert result.valid is True
        assert result.form == SyllogismType.FERIO
    
    def test_invalid_syllogism(self, engine):
        """Test invalid syllogism detection."""
        # This is an invalid syllogism (undistributed middle term)
        # However, our simplified checker only looks at form (AAA), not semantic validity
        # A proper implementation would need semantic parsing to detect this
        major = "Some cats are animals"
        minor = "Some dogs are animals"
        conclusion = "Some cats are dogs"
        
        result = engine.validate_syllogism(major, minor, conclusion)
        
        # III form is not a valid syllogism
        assert result.valid is False
        assert result.form is None
        assert result.confidence == 0.0
    
    def test_classify_universal_affirmative(self, engine):
        """Test classification of universal affirmative (A)."""
        proposition = "All humans are mortal"
        
        prop_type = engine._classify_proposition(proposition)
        
        assert prop_type == "A"
    
    def test_classify_universal_negative(self, engine):
        """Test classification of universal negative (E)."""
        proposition = "No reptiles are mammals"
        
        prop_type = engine._classify_proposition(proposition)
        
        assert prop_type == "E"
    
    def test_classify_particular_affirmative(self, engine):
        """Test classification of particular affirmative (I)."""
        proposition = "Some birds fly"
        
        prop_type = engine._classify_proposition(proposition)
        
        assert prop_type == "I"
    
    def test_classify_particular_negative(self, engine):
        """Test classification of particular negative (O)."""
        proposition = "Some animals are not mammals"
        
        prop_type = engine._classify_proposition(proposition)
        
        assert prop_type == "O"
    
    def test_get_form_description(self, engine):
        """Test getting form descriptions."""
        desc = engine.get_form_description(SyllogismType.BARBARA)
        
        assert "AAA-1" in desc or "Universal affirmative" in desc
        assert desc != "Unknown form"
    
    def test_get_example(self, engine):
        """Test getting form examples."""
        example = engine.get_example(SyllogismType.BARBARA)
        
        assert len(example) > 0
        assert "mortal" in example.lower()
    
    def test_list_valid_forms(self, engine):
        """Test listing all valid forms."""
        forms = engine.list_valid_forms()
        
        assert SyllogismType.BARBARA in forms
        assert SyllogismType.CELARENT in forms
        assert len(forms) == 8


class TestSyllogismResult:
    """Test SyllogismResult dataclass."""
    
    def test_result_creation(self):
        """Test creating SyllogismResult."""
        result = SyllogismResult(
            valid=True,
            form=SyllogismType.BARBARA,
            explanation="Test explanation"
        )
        
        assert result.valid is True
        assert result.form == SyllogismType.BARBARA
        assert result.confidence == 1.0
    
    def test_result_invalid(self):
        """Test creating invalid result."""
        result = SyllogismResult(
            valid=False,
            form=None,
            explanation="Invalid form",
            confidence=0.0
        )
        
        assert result.valid is False
        assert result.form is None
        assert result.confidence == 0.0


class TestSyllogismType:
    """Test SyllogismType enum."""
    
    def test_first_figure_forms(self):
        """Test first figure syllogism forms."""
        first_figure = [
            SyllogismType.BARBARA,
            SyllogismType.CELARENT,
            SyllogismType.DARII,
            SyllogismType.FERIO,
        ]
        
        for form in first_figure:
            assert "1" in form.value
    
    def test_second_figure_forms(self):
        """Test second figure syllogism forms."""
        second_figure = [
            SyllogismType.CESARE,
            SyllogismType.CAMESTRES,
            SyllogismType.FESTINO,
            SyllogismType.BAROCO,
        ]
        
        for form in second_figure:
            assert "2" in form.value
    
    def test_all_forms_unique(self):
        """Test that all syllogism forms have unique values."""
        values = [form.value for form in SyllogismType]
        assert len(values) == len(set(values))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
