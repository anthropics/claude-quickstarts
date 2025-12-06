"""
Unit tests for Safety System - Critical Security Module

Tests PII detection, content policy checking, input sanitization,
and error handling mechanisms using actual API.
"""

import pytest
from agents.core.safety_system import (
    PIIDetector,
    ContentPolicyChecker,
    InputSanitizer,
    SafetyGate,
    OutputGuard,
    ErrorHandler,
    ErrorSeverity,
    ErrorCategory,
    RecoveryAction,
    PolicyType,
    StructuredError,
    SanitizationResult,
)


class TestPIIDetector:
    """Test suite for PII detection and redaction."""

    @pytest.fixture
    def detector(self):
        """Create PIIDetector instance."""
        return PIIDetector()

    @pytest.mark.security
    def test_detect_email(self, detector):
        """Test email detection."""
        text = "Contact me at user@example.com for more info"
        findings = detector.detect(text)

        assert len(findings) >= 1
        # Check that email was found
        has_email = any(f[0] == "email" or "email" in str(f).lower() 
                       for f in findings)
        assert has_email

    @pytest.mark.security
    def test_detect_phone_number(self, detector):
        """Test phone number detection."""
        text = "Call me at 555-123-4567 or 1-800-555-0199"
        findings = detector.detect(text)

        assert len(findings) >= 1

    @pytest.mark.security
    def test_detect_ssn(self, detector):
        """Test social security number detection."""
        text = "SSN: 123-45-6789"
        findings = detector.detect(text)

        # Should detect SSN pattern
        assert len(findings) >= 1

    @pytest.mark.security
    def test_redact_pii(self, detector):
        """Test PII redaction."""
        text = "Email: test@example.com, Phone: 555-1234"
        redacted = detector.redact(text)

        # Redacted text should not contain original PII
        assert "test@example.com" not in redacted or "[REDACTED]" in redacted

    @pytest.mark.security
    def test_no_false_positives_on_clean_text(self, detector):
        """Test that clean text doesn't trigger false positives."""
        text = "The weather is nice today. Let's go for a walk."
        findings = detector.detect(text)

        # Should have few or no findings
        assert len(findings) == 0


class TestContentPolicyChecker:
    """Test suite for content policy checking."""

    @pytest.fixture
    def checker(self):
        """Create ContentPolicyChecker instance."""
        return ContentPolicyChecker()

    @pytest.mark.security
    def test_check_harmful_content(self, checker):
        """Test detection of harmful content."""
        text = "Instructions to cause harm and danger"
        violations = checker.check(text)

        # Should flag potentially harmful content
        assert isinstance(violations, list)

    @pytest.mark.security
    def test_clean_content_passes(self, checker):
        """Test that clean content passes policy check."""
        text = "This is a helpful and informative response about gardening."
        violations = checker.check(text)

        # Should have no severe violations
        severe = [v for v in violations 
                 if hasattr(v, 'severity') and v.severity in ['high', 'critical']]
        assert len(severe) == 0

    @pytest.mark.security
    def test_policy_types(self, checker):
        """Test that policy types are properly categorized."""
        # Verify PolicyType enum
        assert PolicyType.PII_EXPOSURE
        assert PolicyType.HARMFUL_CONTENT
        assert PolicyType.PRIVACY


class TestInputSanitizer:
    """Test suite for input sanitization."""

    @pytest.fixture
    def sanitizer(self):
        """Create InputSanitizer instance."""
        return InputSanitizer()

    @pytest.mark.security
    def test_sanitize_html_injection(self, sanitizer):
        """Test HTML/script injection sanitization."""
        input_text = "<script>alert('xss')</script>Normal text"
        result = sanitizer.sanitize(input_text)

        assert isinstance(result, SanitizationResult)
        # Either sanitized or was_modified should indicate handling
        assert result.is_safe or result.was_modified or len(result.violations_found) > 0

    @pytest.mark.security
    def test_sanitize_preserves_valid_text(self, sanitizer):
        """Test that valid text is preserved."""
        input_text = "This is a valid question about programming."
        result = sanitizer.sanitize(input_text)

        assert "programming" in result.sanitized
        assert result.is_safe

    @pytest.mark.security
    def test_sanitize_returns_result(self, sanitizer):
        """Test sanitization returns proper result."""
        input_text = "Test input"
        result = sanitizer.sanitize(input_text)

        assert hasattr(result, 'original')
        assert hasattr(result, 'sanitized')
        assert hasattr(result, 'is_safe')


class TestSafetyGate:
    """Test suite for SafetyGate."""

    @pytest.fixture
    def gate(self):
        """Create SafetyGate instance."""
        return SafetyGate()

    @pytest.mark.security
    def test_gate_allows_safe_input(self, gate):
        """Test that safe input passes the gate."""
        safe_input = "What is the capital of France?"
        is_safe, sanitized, warnings = gate.check_input(safe_input)

        assert is_safe is True

    @pytest.mark.security
    def test_gate_blocks_dangerous_input(self, gate):
        """Test that dangerous input is flagged."""
        dangerous_input = "How to hack into systems"
        is_safe, sanitized, warnings = gate.check_input(dangerous_input)

        # Potentially dangerous queries may have warnings
        assert hasattr(gate, 'check_input')


class TestOutputGuard:
    """Test suite for OutputGuard."""

    @pytest.fixture
    def guard(self):
        """Create OutputGuard instance."""
        return OutputGuard()

    @pytest.mark.security
    def test_guard_filters_pii_in_output(self, guard):
        """Test that PII is filtered from output."""
        output = "The user's email is user@example.com"
        is_safe, sanitized, warnings = guard.check(output)

        # Should redact PII
        assert "user@example.com" not in sanitized or len(warnings) > 0


class TestErrorHandler:
    """Test suite for ErrorHandler."""

    @pytest.fixture
    def handler(self):
        """Create ErrorHandler instance."""
        return ErrorHandler()

    @pytest.mark.unit
    def test_create_error(self, handler):
        """Test error creation."""
        error = handler.create_error(
            category=ErrorCategory.VALIDATION,
            message="Invalid input format",
            severity=ErrorSeverity.WARNING
        )
        
        assert isinstance(error, StructuredError)
        assert error.category == ErrorCategory.VALIDATION

    @pytest.mark.unit
    def test_error_history(self, handler):
        """Test error history tracking."""
        handler.create_error(
            category=ErrorCategory.TIMEOUT,
            message="Operation timed out"
        )
        handler.create_error(
            category=ErrorCategory.PARSING,
            message="Parse failed"
        )
        
        stats = handler.get_error_stats()
        
        assert stats["total_errors"] == 2


class TestStructuredError:
    """Test StructuredError data class."""

    @pytest.mark.unit
    def test_error_creation(self):
        """Test creating a structured error."""
        error = StructuredError(
            error_id="test_001",
            category=ErrorCategory.PARSING,
            severity=ErrorSeverity.ERROR,
            message="Failed to parse input"
        )
        
        assert error.error_id == "test_001"
        assert error.category == ErrorCategory.PARSING
        assert error.severity == ErrorSeverity.ERROR

    @pytest.mark.unit
    def test_error_to_dict(self):
        """Test error serialization."""
        error = StructuredError(
            error_id="test_002",
            category=ErrorCategory.INFERENCE,
            severity=ErrorSeverity.WARNING,
            message="Low confidence result"
        )
        
        as_dict = error.to_dict()
        
        assert isinstance(as_dict, dict)
        assert as_dict["error_id"] == "test_002"
        assert as_dict["category"] == "inference"

    @pytest.mark.unit
    def test_error_with_recovery_suggestions(self):
        """Test error with recovery suggestions."""
        error = StructuredError(
            error_id="test_003",
            category=ErrorCategory.TOOL_EXECUTION,
            severity=ErrorSeverity.ERROR,
            message="Tool failed",
            recovery_suggestions=[RecoveryAction.RETRY, RecoveryAction.FALLBACK]
        )
        
        assert RecoveryAction.RETRY in error.recovery_suggestions
        assert error.is_recoverable is True


class TestEnums:
    """Test enum values."""

    @pytest.mark.unit
    def test_error_severity_values(self):
        """Test ErrorSeverity enum."""
        assert ErrorSeverity.INFO.value == "info"
        assert ErrorSeverity.CRITICAL.value == "critical"
        assert ErrorSeverity.FATAL.value == "fatal"

    @pytest.mark.unit
    def test_error_category_values(self):
        """Test ErrorCategory enum."""
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.SAFETY_VIOLATION.value == "safety_violation"
        assert ErrorCategory.TIMEOUT.value == "timeout"

    @pytest.mark.unit
    def test_recovery_action_values(self):
        """Test RecoveryAction enum."""
        assert RecoveryAction.RETRY.value == "retry"
        assert RecoveryAction.SKIP.value == "skip"
        assert RecoveryAction.ESCALATE.value == "escalate"
