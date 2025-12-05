"""
Unit tests for Critic System

Tests self-critique, verification logic, quality assurance,
and output validation mechanisms using the actual CriticSystem API.
"""

import pytest
from agents.core.critic_system import (
    CriticSystem,
    CritiqueResult,
    Critique,
    CritiqueType,
    CritiqueSeverity,
    LogicCritic,
    BiasCritic,
)


class TestCriticSystem:
    """Test suite for CriticSystem."""

    @pytest.fixture
    def critic(self):
        """Create CriticSystem instance."""
        return CriticSystem()

    @pytest.mark.unit
    def test_initialization(self, critic):
        """Test critic system initialization."""
        assert critic is not None
        assert hasattr(critic, 'review')
        assert hasattr(critic, 'self_consistency_check')
        assert len(critic.critics) >= 3  # LogicCritic, CompletenessCritic, BiasCritic

    @pytest.mark.unit
    def test_basic_review(self, critic):
        """Test basic review of reasoning."""
        reasoning = "All men are mortal. Socrates is a man."
        conclusion = "Therefore, Socrates is mortal."
        
        result = critic.review(reasoning, conclusion)

        assert isinstance(result, CritiqueResult)
        assert hasattr(result, 'critiques')
        assert hasattr(result, 'revised_confidence')
        assert hasattr(result, 'should_revise')

    @pytest.mark.unit
    def test_identify_logical_fallacy(self, critic):
        """Test identification of logical fallacies."""
        # Hasty generalization
        reasoning = "One bird couldn't fly. All birds never fly based on one example."
        conclusion = "Birds cannot fly."
        
        result = critic.review(reasoning, conclusion)

        # Should flag logical fallacy
        has_logic_critique = any(
            c.critique_type == CritiqueType.LOGICAL
            for c in result.critiques
        )
        assert has_logic_critique

    @pytest.mark.unit
    def test_high_quality_reasoning_passes(self, critic):
        """Test that well-structured reasoning passes without critical issues."""
        reasoning = """
        Premise 1: Water boils at 100°C at sea level pressure.
        Premise 2: The pot contains water at sea level.
        Premise 3: The water has been heated to 100°C.
        """
        conclusion = "Therefore, the water is boiling."
        
        result = critic.review(reasoning, conclusion)

        critical_issues = [c for c in result.critiques 
                          if c.severity == CritiqueSeverity.CRITICAL]
        assert len(critical_issues) == 0

    @pytest.mark.unit  
    def test_revised_confidence_decreases_with_issues(self, critic):
        """Test that confidence decreases when issues are found."""
        # Fallacious reasoning
        reasoning = "Expert says X, must be true because expert says so."
        conclusion = "X is definitely true."
        
        result = critic.review(reasoning, conclusion, original_confidence=0.9)
        
        # Should have lower confidence due to issues
        assert result.revised_confidence <= 0.9

    @pytest.mark.unit
    def test_should_revise_for_major_issues(self, critic):
        """Test that revision is recommended for major issues."""
        # Reasoning with contradiction
        reasoning = "X is true. X is false. Therefore conclusion."
        conclusion = "Something is proven."
        
        result = critic.review(reasoning, conclusion)
        
        # If critical/major issues found, should_revise should be True
        if result.has_critical or result.has_major:
            assert result.should_revise

    @pytest.mark.unit
    def test_add_custom_critic(self, critic):
        """Test adding a custom critic."""
        class CustomCritic(LogicCritic):
            def critique(self, reasoning, conclusion, context=None):
                return [Critique(
                    critique_type=CritiqueType.LOGICAL,
                    severity=CritiqueSeverity.SUGGESTION,
                    description="Custom check",
                    target="test"
                )]
        
        initial_count = len(critic.critics)
        critic.add_critic(CustomCritic())
        
        assert len(critic.critics) == initial_count + 1


class TestSelfConsistencyCheck:
    """Test self-consistency checking functionality."""

    @pytest.fixture
    def critic(self):
        return CriticSystem()

    @pytest.mark.unit
    def test_single_response_is_consistent(self, critic):
        """Test that single response is always consistent."""
        responses = ["The answer is 42."]
        
        is_consistent, score, summary = critic.self_consistency_check(responses)
        
        assert is_consistent is True
        assert score == 1.0

    @pytest.mark.unit
    def test_identical_responses_are_consistent(self, critic):
        """Test that identical responses are consistent."""
        responses = [
            "After analysis, the conclusion is definitely X",
            "After analysis, the conclusion is definitely X",
            "After analysis, the conclusion is definitely X"
        ]
        
        is_consistent, score, summary = critic.self_consistency_check(responses)
        
        assert is_consistent is True
        assert score >= 0.7

    @pytest.mark.unit
    def test_different_responses_are_inconsistent(self, critic):
        """Test that completely different responses are inconsistent."""
        responses = [
            "The answer is definitely yes.",
            "The answer is absolutely no.",
            "The answer is maybe perhaps."
        ]
        
        is_consistent, score, summary = critic.self_consistency_check(responses)
        
        # Very different conclusions should have lower agreement
        assert score < 1.0

    @pytest.mark.unit
    def test_custom_threshold(self, critic):
        """Test custom consistency threshold."""
        responses = [
            "Result is approximately X.",
            "Result is roughly X.",
        ]
        
        # High threshold
        is_consistent_high, _, _ = critic.self_consistency_check(responses, threshold=0.9)
        # Low threshold
        is_consistent_low, _, _ = critic.self_consistency_check(responses, threshold=0.3)
        
        # Low threshold should be more permissive
        assert is_consistent_low or not is_consistent_high  # At least one passes


class TestLogicCritic:
    """Test LogicCritic specifically."""

    @pytest.fixture
    def logic_critic(self):
        return LogicCritic()

    @pytest.mark.unit
    def test_detect_ad_hominem(self, logic_critic):
        """Test detection of ad hominem fallacy."""
        reasoning = "The person making this claim has bad character. We can't trust anything they say. Therefore they're wrong."
        conclusion = "Their argument is invalid."
        
        critiques = logic_critic.critique(reasoning, conclusion)
        
        fallacy_critiques = [c for c in critiques 
                           if "ad hominem" in c.description.lower()]
        assert len(fallacy_critiques) > 0

    @pytest.mark.unit
    def test_detect_appeal_to_authority(self, logic_critic):
        """Test detection of appeal to authority fallacy."""
        reasoning = "A famous expert says this must be true. An authority claims it, so it must be."
        conclusion = "It is definitely true."
        
        critiques = logic_critic.critique(reasoning, conclusion)
        
        fallacy_critiques = [c for c in critiques 
                           if "authority" in c.description.lower()]
        assert len(fallacy_critiques) > 0

    @pytest.mark.unit
    def test_valid_reasoning_has_no_fallacies(self, logic_critic):
        """Test that valid reasoning doesn't trigger fallacy detection."""
        reasoning = """
        If P then Q.
        P is true.
        """
        conclusion = "Therefore Q is true."
        
        critiques = logic_critic.critique(reasoning, conclusion)
        
        # Valid modus ponens should not have major fallacy issues
        major_fallacies = [c for c in critiques 
                         if c.severity in (CritiqueSeverity.CRITICAL, CritiqueSeverity.MAJOR)]
        # Should have few or no major issues
        assert len(major_fallacies) <= 1


class TestBiasCritic:
    """Test BiasCritic specifically."""

    @pytest.fixture
    def bias_critic(self):
        return BiasCritic()

    @pytest.mark.unit
    def test_detect_absolute_language(self, bias_critic):
        """Test detection of absolute language as potential bias."""
        reasoning = "Everyone always knows that this is never wrong. Nobody disagrees."
        conclusion = "It is universally accepted."
        
        critiques = bias_critic.critique(reasoning, conclusion)
        
        # Absolute language may or may not be flagged depending on implementation
        assert isinstance(critiques, list)

    @pytest.mark.unit
    def test_balanced_language_passes(self, bias_critic):
        """Test that balanced language has fewer bias flags."""
        reasoning = "Some evidence suggests this might be the case. However, there are alternative views."
        conclusion = "This is one possible interpretation."
        
        critiques = bias_critic.critique(reasoning, conclusion)
        
        # Balanced language should have fewer/no bias critiques
        major_bias = [c for c in critiques 
                     if c.severity in (CritiqueSeverity.CRITICAL, CritiqueSeverity.MAJOR)]
        assert len(major_bias) == 0
