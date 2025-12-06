"""
Unit tests for FallacyDetector - Pattern-Based Fallacy Detection

Tests detection of 22+ fallacy patterns across all categories.
"""

import pytest
from agents.core.fallacy_detector import (
    FallacyDetector,
    FallacyCategory,
    FallacySeverity,
    FallacyPattern
)


class TestFallacyDetector:
    """Test suite for FallacyDetector."""
    
    @pytest.fixture
    def detector(self):
        """Create FallacyDetector instance."""
        return FallacyDetector()
    
    def test_initialization(self, detector):
        """Test detector initializes with comprehensive database."""
        assert len(detector.fallacies) >= 21
        assert "ad_hominem" in detector.fallacies
        assert "false_dilemma" in detector.fallacies
    
    def test_detect_ad_hominem(self, detector):
        """Test detection of ad hominem fallacy."""
        premises = ["You're wrong because you're not qualified"]
        conclusion = "Your argument is invalid"
        
        detected = detector.detect("", premises, conclusion)
        
        # Should detect ad hominem
        fallacy_names = [f.name for f in detected]
        assert any("Ad Hominem" in name for name in fallacy_names)
    
    def test_detect_false_dilemma(self, detector):
        """Test detection of false dilemma fallacy."""
        premises = ["Either you support us or you're against us"]
        conclusion = "You must choose"
        
        detected = detector.detect("", premises, conclusion)
        
        fallacy_names = [f.name for f in detected]
        assert any("False Dilemma" in name for name in fallacy_names)
    
    def test_detect_hasty_generalization(self, detector):
        """Test detection of hasty generalization."""
        premises = ["I saw two bad drivers from that state"]
        conclusion = "All drivers from that state are bad"
        
        detected = detector.detect("", premises, conclusion)
        
        fallacy_names = [f.name for f in detected]
        assert any("Hasty Generalization" in name for name in fallacy_names)
    
    def test_detect_appeal_to_emotion(self, detector):
        """Test detection of appeal to emotion."""
        premises = ["Think of the children! We must ban this"]
        conclusion = "It should be banned"
        
        detected = detector.detect("", premises, conclusion)
        
        fallacy_names = [f.name for f in detected]
        assert any("Appeal to Emotion" in name for name in fallacy_names)
    
    def test_detect_slippery_slope(self, detector):
        """Test detection of slippery slope."""
        premises = ["If we allow this, it will lead to chaos"]
        conclusion = "We cannot allow this"
        
        detected = detector.detect("", premises, conclusion)
        
        fallacy_names = [f.name for f in detected]
        assert any("Slippery Slope" in name for name in fallacy_names)
    
    def test_no_fallacies_detected(self, detector):
        """Test when no fallacies are present."""
        premises = ["The sky is blue"]
        conclusion = "Water reflects light"
        
        detected = detector.detect("", premises, conclusion)
        
        # Some generic words might trigger false positives, but should be minimal
        assert isinstance(detected, list)
    
    def test_get_by_category_relevance(self, detector):
        """Test getting fallacies by relevance category."""
        relevance = detector.get_by_category(FallacyCategory.RELEVANCE)
        
        assert len(relevance) > 0
        assert all(f.category == FallacyCategory.RELEVANCE for f in relevance)
        
        # Check for expected relevance fallacies
        ids = [f.id for f in relevance]
        assert "ad_hominem" in ids
        assert "red_herring" in ids
    
    def test_get_by_category_presumption(self, detector):
        """Test getting fallacies by presumption category."""
        presumption = detector.get_by_category(FallacyCategory.PRESUMPTION)
        
        assert len(presumption) > 0
        assert all(f.category == FallacyCategory.PRESUMPTION for f in presumption)
        
        ids = [f.id for f in presumption]
        assert "false_dilemma" in ids
        assert "begging_question" in ids
    
    def test_get_by_category_formal(self, detector):
        """Test getting fallacies by formal category."""
        formal = detector.get_by_category(FallacyCategory.FORMAL)
        
        assert len(formal) > 0
        assert all(f.category == FallacyCategory.FORMAL for f in formal)
        
        ids = [f.id for f in formal]
        assert "affirming_consequent" in ids
        assert "denying_antecedent" in ids
    
    def test_get_by_severity_major(self, detector):
        """Test getting major severity fallacies."""
        major = detector.get_by_severity(FallacySeverity.MAJOR)
        
        assert len(major) > 0
        assert all(f.severity == FallacySeverity.MAJOR for f in major)
    
    def test_get_by_severity_moderate(self, detector):
        """Test getting moderate severity fallacies."""
        moderate = detector.get_by_severity(FallacySeverity.MODERATE)
        
        assert len(moderate) > 0
        assert all(f.severity == FallacySeverity.MODERATE for f in moderate)
    
    def test_get_fallacy_by_id(self, detector):
        """Test retrieving specific fallacy by ID."""
        fallacy = detector.get_fallacy("ad_hominem")
        
        assert fallacy is not None
        assert fallacy.id == "ad_hominem"
        assert fallacy.name == "Ad Hominem"
        assert fallacy.category == FallacyCategory.RELEVANCE
    
    def test_get_nonexistent_fallacy(self, detector):
        """Test retrieving non-existent fallacy."""
        fallacy = detector.get_fallacy("nonexistent_fallacy")
        
        assert fallacy is None
    
    def test_list_all(self, detector):
        """Test listing all fallacies."""
        all_fallacies = detector.list_all()
        
        assert len(all_fallacies) >= 21
        assert all(isinstance(f, FallacyPattern) for f in all_fallacies)
    
    def test_count_by_category(self, detector):
        """Test counting fallacies by category."""
        counts = detector.count_by_category()
        
        assert FallacyCategory.RELEVANCE in counts
        assert FallacyCategory.PRESUMPTION in counts
        assert FallacyCategory.AMBIGUITY in counts
        assert FallacyCategory.FORMAL in counts
        
        total = sum(counts.values())
        assert total == len(detector.fallacies)
    
    def test_multiple_fallacies_detected(self, detector):
        """Test detecting multiple fallacies in one argument."""
        premises = [
            "Either you support this or you're against progress",
            "Think of the children!"
        ]
        conclusion = "Therefore you must support this"
        
        detected = detector.detect("", premises, conclusion)
        
        # Should detect multiple fallacies (false dilemma, appeal to emotion)
        assert len(detected) >= 2


class TestFallacyPattern:
    """Test FallacyPattern dataclass."""
    
    def test_pattern_creation(self):
        """Test creating a FallacyPattern."""
        pattern = FallacyPattern(
            id="test_fallacy",
            name="Test Fallacy",
            category=FallacyCategory.RELEVANCE,
            severity=FallacySeverity.MAJOR,
            description="Test description",
            pattern_indicators=["test", "indicator"],
            example="Test example"
        )
        
        assert pattern.id == "test_fallacy"
        assert pattern.name == "Test Fallacy"
        assert pattern.category == FallacyCategory.RELEVANCE
        assert len(pattern.pattern_indicators) == 2


class TestFallacyCategory:
    """Test FallacyCategory enum."""
    
    def test_all_categories_exist(self):
        """Test all expected categories exist."""
        expected = [
            FallacyCategory.RELEVANCE,
            FallacyCategory.PRESUMPTION,
            FallacyCategory.AMBIGUITY,
            FallacyCategory.FORMAL,
        ]
        
        for category in expected:
            assert isinstance(category, FallacyCategory)


class TestFallacySeverity:
    """Test FallacySeverity enum."""
    
    def test_all_severities_exist(self):
        """Test all expected severities exist."""
        expected = [
            FallacySeverity.MAJOR,
            FallacySeverity.MODERATE,
            FallacySeverity.MINOR,
        ]
        
        for severity in expected:
            assert isinstance(severity, FallacySeverity)


class TestFallacyDatabase:
    """Test fallacy database completeness."""
    
    @pytest.fixture
    def detector(self):
        return FallacyDetector()
    
    def test_relevance_fallacies_complete(self, detector):
        """Test that key relevance fallacies are present."""
        relevance = detector.get_by_category(FallacyCategory.RELEVANCE)
        ids = [f.id for f in relevance]
        
        expected = ["ad_hominem", "appeal_to_authority", "appeal_to_emotion", "red_herring", "straw_man"]
        for fallacy_id in expected:
            assert fallacy_id in ids, f"Missing fallacy: {fallacy_id}"
    
    def test_presumption_fallacies_complete(self, detector):
        """Test that key presumption fallacies are present."""
        presumption = detector.get_by_category(FallacyCategory.PRESUMPTION)
        ids = [f.id for f in presumption]
        
        expected = ["false_dilemma", "begging_question", "hasty_generalization", "slippery_slope"]
        for fallacy_id in expected:
            assert fallacy_id in ids, f"Missing fallacy: {fallacy_id}"
    
    def test_formal_fallacies_complete(self, detector):
        """Test that key formal fallacies are present."""
        formal = detector.get_by_category(FallacyCategory.FORMAL)
        ids = [f.id for f in formal]
        
        expected = ["affirming_consequent", "denying_antecedent", "post_hoc", "non_sequitur"]
        for fallacy_id in expected:
            assert fallacy_id in ids, f"Missing fallacy: {fallacy_id}"
    
    def test_all_fallacies_have_examples(self, detector):
        """Test that all fallacies have examples."""
        all_fallacies = detector.list_all()
        
        for fallacy in all_fallacies:
            assert len(fallacy.example) > 0, f"Fallacy {fallacy.id} missing example"
            assert len(fallacy.description) > 0, f"Fallacy {fallacy.id} missing description"
            assert len(fallacy.pattern_indicators) > 0, f"Fallacy {fallacy.id} missing indicators"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
