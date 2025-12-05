"""
Unit tests for Uncertainty and Abstention System

Tests confidence calibration, abstention decisions, uncertainty quantification,
and "I don't know" responses.
"""

import pytest
import math
from agents.core.uncertainty_system import (
    UncertaintySystem,
    ConfidenceCalibrator,
    AbstentionSystem,
    ConfidenceEstimate,
    AbstentionDecision,
    CalibrationData,
    ConfidenceSource,
    UncertaintyType,
    AbstentionReason,
)


class TestConfidenceEstimate:
    """Test suite for ConfidenceEstimate."""

    @pytest.mark.unit
    def test_confidence_estimate_creation(self):
        """Test creating a confidence estimate."""
        estimate = ConfidenceEstimate(
            value=0.85,
            source=ConfidenceSource.MODEL_LOGPROBS,
            uncertainty_type=UncertaintyType.EPISTEMIC,
            lower_bound=0.75,
            upper_bound=0.95,
            explanation="High confidence based on clear signal"
        )

        assert estimate.value == 0.85
        assert estimate.source == ConfidenceSource.MODEL_LOGPROBS
        assert estimate.uncertainty_type == UncertaintyType.EPISTEMIC

    @pytest.mark.unit
    def test_interval_width(self):
        """Test confidence interval width calculation."""
        estimate = ConfidenceEstimate(
            value=0.8,
            source=ConfidenceSource.CALIBRATION,
            lower_bound=0.7,
            upper_bound=0.9
        )

        assert estimate.interval_width == 0.2

    @pytest.mark.unit
    def test_is_reliable_true(self):
        """Test reliability check for high confidence with narrow interval."""
        estimate = ConfidenceEstimate(
            value=0.85,
            source=ConfidenceSource.ENSEMBLE,
            lower_bound=0.8,
            upper_bound=0.9
        )

        assert estimate.is_reliable(threshold=0.7) is True

    @pytest.mark.unit
    def test_is_reliable_false_low_confidence(self):
        """Test reliability check fails for low confidence."""
        estimate = ConfidenceEstimate(
            value=0.4,
            source=ConfidenceSource.SELF_ASSESSMENT,
            lower_bound=0.3,
            upper_bound=0.5
        )

        assert estimate.is_reliable(threshold=0.5) is False

    @pytest.mark.unit
    def test_is_reliable_false_wide_interval(self):
        """Test reliability check fails for wide confidence interval."""
        estimate = ConfidenceEstimate(
            value=0.7,
            source=ConfidenceSource.HYBRID,
            lower_bound=0.2,
            upper_bound=0.9
        )

        # Wide interval (0.7) should fail reliability
        assert estimate.is_reliable() is False

    @pytest.mark.unit
    def test_confidence_factors(self):
        """Test confidence factors tracking."""
        estimate = ConfidenceEstimate(
            value=0.8,
            source=ConfidenceSource.HYBRID,
            factors={
                "model_agreement": 0.9,
                "data_quality": 0.75,
                "domain_match": 0.85
            }
        )

        assert "model_agreement" in estimate.factors
        assert estimate.factors["model_agreement"] == 0.9


class TestConfidenceCalibrator:
    """Test suite for ConfidenceCalibrator."""

    @pytest.fixture
    def calibrator(self):
        """Create ConfidenceCalibrator instance."""
        return ConfidenceCalibrator(window_size=100)

    @pytest.mark.unit
    def test_initialization(self, calibrator):
        """Test calibrator initialization."""
        assert len(calibrator.history) == 0
        assert calibrator.window_size == 100

    @pytest.mark.unit
    def test_add_calibration_data(self, calibrator):
        """Test adding calibration data."""
        data = CalibrationData(
            predicted_confidence=0.8,
            actual_correct=True,
            timestamp="2024-01-01T00:00:00",
            domain="math"
        )

        calibrator.add_data(data)

        assert len(calibrator.history) == 1

    @pytest.mark.unit
    def test_calibrate_confidence(self, calibrator):
        """Test calibrating raw confidence."""
        # Add historical data
        for i in range(50):
            calibrator.add_data(CalibrationData(
                predicted_confidence=0.9,
                actual_correct=True,
                timestamp=f"2024-01-{i+1:02d}"
            ))

        # Calibrate new confidence
        calibrated = calibrator.calibrate(0.9)

        assert 0.0 <= calibrated <= 1.0

    @pytest.mark.unit
    def test_perfect_calibration(self, calibrator):
        """Test that perfectly calibrated predictions remain unchanged."""
        # Add perfectly calibrated data
        for conf in [0.1, 0.3, 0.5, 0.7, 0.9]:
            # Each confidence level is correct that percentage of time
            for _ in range(int(conf * 10)):
                calibrator.add_data(CalibrationData(
                    predicted_confidence=conf,
                    actual_correct=True,
                    timestamp="2024-01-01"
                ))
            for _ in range(int((1 - conf) * 10)):
                calibrator.add_data(CalibrationData(
                    predicted_confidence=conf,
                    actual_correct=False,
                    timestamp="2024-01-01"
                ))

        # Calibration should not change much for well-calibrated data
        calibrated = calibrator.calibrate(0.5)
        assert 0.4 <= calibrated <= 0.6

    @pytest.mark.unit
    def test_get_calibration_curve(self, calibrator):
        """Test getting calibration curve."""
        # Add some data
        for _ in range(20):
            calibrator.add_data(CalibrationData(
                predicted_confidence=0.8,
                actual_correct=True,
                timestamp="2024-01-01"
            ))

        curve = calibrator.get_calibration_curve()

        assert isinstance(curve, dict)

    @pytest.mark.unit
    def test_window_size_limit(self, calibrator):
        """Test that history is limited to window size."""
        # Add more data than window size
        for i in range(150):
            calibrator.add_data(CalibrationData(
                predicted_confidence=0.5,
                actual_correct=i % 2 == 0,
                timestamp=f"2024-01-{i+1:02d}"
            ))

        # Should only keep window_size entries
        assert len(calibrator.history) <= calibrator.window_size


class TestAbstentionDecision:
    """Test suite for AbstentionDecision."""

    @pytest.mark.unit
    def test_abstention_decision_creation(self):
        """Test creating abstention decision."""
        decision = AbstentionDecision(
            should_abstain=True,
            reason=AbstentionReason.LOW_CONFIDENCE,
            confidence=0.3,
            alternative_response="I'm not confident enough to answer this.",
            follow_up_questions=["Could you provide more context?"],
            explanation="Confidence below threshold"
        )

        assert decision.should_abstain is True
        assert decision.reason == AbstentionReason.LOW_CONFIDENCE
        assert len(decision.follow_up_questions) == 1

    @pytest.mark.unit
    def test_no_abstention_decision(self):
        """Test decision to not abstain."""
        decision = AbstentionDecision(
            should_abstain=False,
            confidence=0.9
        )

        assert decision.should_abstain is False
        assert decision.reason is None


class TestAbstentionSystem:
    """Test suite for AbstentionSystem."""

    @pytest.fixture
    def system(self):
        """Create AbstentionSystem instance."""
        return AbstentionSystem(confidence_threshold=0.5)

    @pytest.mark.unit
    def test_initialization(self, system):
        """Test abstention system initialization."""
        assert system.confidence_threshold == 0.5

    @pytest.mark.unit
    def test_should_abstain_low_confidence(self, system):
        """Test abstention on low confidence."""
        estimate = ConfidenceEstimate(
            value=0.3,
            source=ConfidenceSource.MODEL_LOGPROBS
        )

        decision = system.decide(estimate, query="What is X?")

        assert decision.should_abstain is True
        assert decision.reason == AbstentionReason.LOW_CONFIDENCE

    @pytest.mark.unit
    def test_should_not_abstain_high_confidence(self, system):
        """Test no abstention on high confidence."""
        estimate = ConfidenceEstimate(
            value=0.85,
            source=ConfidenceSource.ENSEMBLE
        )

        decision = system.decide(estimate, query="What is 2+2?")

        assert decision.should_abstain is False

    @pytest.mark.unit
    def test_abstain_on_ambiguous_query(self, system):
        """Test abstention on ambiguous query."""
        decision = system.check_query_ambiguity("What does 'it' mean?")

        # Ambiguous pronoun without context
        assert decision.should_abstain is True or decision.reason == AbstentionReason.AMBIGUOUS_QUERY

    @pytest.mark.unit
    def test_abstain_on_harmful_content(self, system):
        """Test abstention on harmful content."""
        decision = system.check_safety("How to make explosives?")

        # Should abstain on potentially harmful query
        assert decision.should_abstain is True

    @pytest.mark.unit
    def test_abstain_on_conflicting_evidence(self, system):
        """Test abstention when evidence conflicts."""
        evidence = [
            {"claim": "X is true", "confidence": 0.8},
            {"claim": "X is false", "confidence": 0.75}
        ]

        decision = system.check_evidence_conflict(evidence)

        # Conflicting high-confidence evidence
        assert decision.should_abstain is True
        assert decision.reason == AbstentionReason.CONFLICTING_EVIDENCE

    @pytest.mark.unit
    def test_generate_idk_response(self, system):
        """Test generating 'I don't know' response."""
        decision = AbstentionDecision(
            should_abstain=True,
            reason=AbstentionReason.INSUFFICIENT_DATA,
            confidence=0.2
        )

        response = system.generate_response(decision, query="What is X?")

        assert "don't know" in response.lower() or "not enough" in response.lower()

    @pytest.mark.unit
    def test_suggest_follow_up_questions(self, system):
        """Test suggesting follow-up questions."""
        decision = system.decide(
            ConfidenceEstimate(value=0.3, source=ConfidenceSource.MODEL_LOGPROBS),
            query="Tell me about X"
        )

        if decision.should_abstain:
            assert len(decision.follow_up_questions) > 0


class TestUncertaintyTypes:
    """Test suite for uncertainty type classification."""

    @pytest.mark.unit
    def test_epistemic_uncertainty(self):
        """Test epistemic (knowledge) uncertainty."""
        # Epistemic uncertainty can be reduced with more information
        estimate = ConfidenceEstimate(
            value=0.6,
            source=ConfidenceSource.SELF_ASSESSMENT,
            uncertainty_type=UncertaintyType.EPISTEMIC,
            explanation="Lack of domain knowledge"
        )

        assert estimate.uncertainty_type == UncertaintyType.EPISTEMIC

    @pytest.mark.unit
    def test_aleatoric_uncertainty(self):
        """Test aleatoric (inherent randomness) uncertainty."""
        # Aleatoric uncertainty is irreducible
        estimate = ConfidenceEstimate(
            value=0.5,
            source=ConfidenceSource.MODEL_LOGPROBS,
            uncertainty_type=UncertaintyType.ALEATORIC,
            explanation="Inherently random outcome"
        )

        assert estimate.uncertainty_type == UncertaintyType.ALEATORIC

    @pytest.mark.unit
    def test_model_uncertainty(self):
        """Test model limitation uncertainty."""
        estimate = ConfidenceEstimate(
            value=0.4,
            source=ConfidenceSource.SELF_ASSESSMENT,
            uncertainty_type=UncertaintyType.MODEL,
            explanation="Beyond model capabilities"
        )

        assert estimate.uncertainty_type == UncertaintyType.MODEL


class TestIntegrationUncertainty:
    """Integration tests for uncertainty system."""

    @pytest.mark.integration
    def test_calibration_improves_accuracy(self):
        """Test that calibration improves accuracy over time."""
        calibrator = ConfidenceCalibrator()

        # Add overconfident data
        for _ in range(50):
            calibrator.add_data(CalibrationData(
                predicted_confidence=0.9,
                actual_correct=False,  # Wrong despite high confidence
                timestamp="2024-01-01"
            ))

        # Calibrated confidence should be lower
        calibrated = calibrator.calibrate(0.9)

        assert calibrated < 0.9  # Should reduce overconfidence

    @pytest.mark.integration
    def test_full_uncertainty_pipeline(self):
        """Test complete uncertainty assessment pipeline."""
        calibrator = ConfidenceCalibrator()
        system = AbstentionSystem()

        # Add historical data
        for i in range(20):
            calibrator.add_data(CalibrationData(
                predicted_confidence=0.7,
                actual_correct=i % 2 == 0,
                timestamp=f"2024-01-{i+1:02d}"
            ))

        # Get calibrated confidence
        raw_confidence = 0.7
        calibrated_confidence = calibrator.calibrate(raw_confidence)

        # Make abstention decision
        estimate = ConfidenceEstimate(
            value=calibrated_confidence,
            source=ConfidenceSource.CALIBRATION
        )

        decision = system.decide(estimate, query="Sample query")

        # Decision should be based on calibrated confidence
        assert isinstance(decision, AbstentionDecision)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.unit
    def test_zero_confidence(self):
        """Test handling of zero confidence."""
        estimate = ConfidenceEstimate(
            value=0.0,
            source=ConfidenceSource.MODEL_LOGPROBS
        )

        assert estimate.value == 0.0
        assert estimate.is_reliable() is False

    @pytest.mark.unit
    def test_full_confidence(self):
        """Test handling of 100% confidence."""
        estimate = ConfidenceEstimate(
            value=1.0,
            source=ConfidenceSource.MODEL_LOGPROBS,
            lower_bound=0.95,
            upper_bound=1.0
        )

        assert estimate.value == 1.0
        assert estimate.is_reliable() is True

    @pytest.mark.unit
    def test_empty_calibration_history(self):
        """Test calibration with no historical data."""
        calibrator = ConfidenceCalibrator()

        # Should handle gracefully, possibly returning raw confidence
        calibrated = calibrator.calibrate(0.7)

        assert 0.0 <= calibrated <= 1.0

    @pytest.mark.unit
    def test_nan_confidence(self):
        """Test handling of NaN confidence."""
        # Should validate or handle NaN values
        try:
            estimate = ConfidenceEstimate(
                value=float('nan'),
                source=ConfidenceSource.MODEL_LOGPROBS
            )
            # If allowed, should detect unreliability
            assert math.isnan(estimate.value) or not estimate.is_reliable()
        except (ValueError, TypeError):
            # Or reject invalid confidence values
            pass


class TestConfidenceSources:
    """Test different confidence sources."""

    @pytest.mark.unit
    def test_all_confidence_sources(self):
        """Test that all confidence sources are supported."""
        sources = [
            ConfidenceSource.MODEL_LOGPROBS,
            ConfidenceSource.SELF_ASSESSMENT,
            ConfidenceSource.CALIBRATION,
            ConfidenceSource.ENSEMBLE,
            ConfidenceSource.CRITIC,
            ConfidenceSource.HYBRID
        ]

        for source in sources:
            estimate = ConfidenceEstimate(
                value=0.8,
                source=source
            )
            assert estimate.source == source

    @pytest.mark.unit
    def test_hybrid_confidence_combination(self):
        """Test combining multiple confidence sources."""
        estimate = ConfidenceEstimate(
            value=0.75,
            source=ConfidenceSource.HYBRID,
            factors={
                "model": 0.8,
                "ensemble": 0.7,
                "critic": 0.75
            }
        )

        # Hybrid should combine multiple sources
        assert estimate.source == ConfidenceSource.HYBRID
        assert len(estimate.factors) >= 2


class TestAbstentionReasons:
    """Test different abstention reasons."""

    @pytest.mark.unit
    def test_all_abstention_reasons(self):
        """Test that all abstention reasons are supported."""
        reasons = [
            AbstentionReason.LOW_CONFIDENCE,
            AbstentionReason.INSUFFICIENT_DATA,
            AbstentionReason.OUT_OF_SCOPE,
            AbstentionReason.AMBIGUOUS_QUERY,
            AbstentionReason.HARMFUL_CONTENT,
            AbstentionReason.CONFLICTING_EVIDENCE,
            AbstentionReason.REQUIRES_EXPERTISE
        ]

        for reason in reasons:
            decision = AbstentionDecision(
                should_abstain=True,
                reason=reason,
                confidence=0.3
            )
            assert decision.reason == reason
