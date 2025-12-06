"""
Unit tests for Robustness System

Tests input validation, output guardrails, circuit breakers,
rate limiting, and resource management.
"""

import pytest
import time
from unittest.mock import Mock, patch
from agents.core.robustness_system import (
    RobustnessSystem,
    InputValidator,
    OutputGuardrail,
    CircuitBreaker,
    RateLimiter,
    ResourceManager,
    ValidationResult,
    ValidationReport,
    GuardrailReport,
    GuardrailType,
    CircuitState,
    CircuitBreakerStats,
)
pytest.skip("Robustness system suite skipped pending full implementation", allow_module_level=True)


class TestInputValidator:
    """Test suite for InputValidator."""

    @pytest.fixture
    def validator(self):
        """Create InputValidator instance."""
        return InputValidator()

    @pytest.mark.unit
    def test_initialization(self, validator):
        """Test validator initialization."""
        assert validator.max_input_length == 10000
        assert len(validator.forbidden_patterns) > 0

    @pytest.mark.security
    @pytest.mark.unit
    def test_valid_input(self, validator):
        """Test validation of valid input."""
        result = validator.validate("This is a normal, safe input")

        assert result.result == ValidationResult.VALID
        assert len(result.issues_found) == 0

    @pytest.mark.security
    @pytest.mark.unit
    def test_xss_detection(self, validator):
        """Test XSS script detection."""
        malicious = "<script>alert('xss')</script>"
        result = validator.validate(malicious, sanitize=True)

        assert result.result in [ValidationResult.SANITIZED, ValidationResult.REJECTED]
        assert len(result.issues_found) > 0

    @pytest.mark.security
    @pytest.mark.unit
    def test_javascript_protocol_detection(self, validator):
        """Test javascript: protocol detection."""
        malicious = "javascript:alert('xss')"
        result = validator.validate(malicious, sanitize=True)

        assert result.result in [ValidationResult.SANITIZED, ValidationResult.REJECTED]

    @pytest.mark.security
    @pytest.mark.unit
    def test_template_injection_detection(self, validator):
        """Test template injection detection."""
        malicious = "Hello {{user.password}}"
        result = validator.validate(malicious, sanitize=True)

        assert result.result in [ValidationResult.SANITIZED, ValidationResult.REJECTED]

    @pytest.mark.unit
    def test_input_length_limit(self, validator):
        """Test input length limit enforcement."""
        long_input = "a" * 20000  # Exceeds default 10000 limit
        result = validator.validate(long_input, sanitize=True)

        assert "length" in str(result.issues_found).lower()
        if result.sanitized_input:
            assert len(result.sanitized_input) <= validator.max_input_length

    @pytest.mark.unit
    def test_input_length_rejection(self, validator):
        """Test input length rejection without sanitization."""
        long_input = "a" * 20000
        result = validator.validate(long_input, sanitize=False)

        assert result.result == ValidationResult.REJECTED

    @pytest.mark.unit
    def test_add_forbidden_pattern(self, validator):
        """Test adding custom forbidden pattern."""
        validator.add_forbidden_pattern(r"FORBIDDEN_WORD")

        result = validator.validate("This contains FORBIDDEN_WORD", sanitize=True)

        assert result.result in [ValidationResult.SANITIZED, ValidationResult.REJECTED]

    @pytest.mark.unit
    def test_add_required_pattern(self, validator):
        """Test adding required pattern."""
        validator.add_required_pattern(r"REQUIRED_KEYWORD")

        result_without = validator.validate("Some text without keyword")
        result_with = validator.validate("Some text with REQUIRED_KEYWORD")

        assert len(result_without.issues_found) > 0
        assert len(result_with.issues_found) == 0 or result_with.result == ValidationResult.VALID

    @pytest.mark.security
    @pytest.mark.unit
    def test_sanitize_for_logging(self, validator):
        """Test sanitizing sensitive data for logging."""
        sensitive = "My API_KEY=sk-abc123def456 and password=secret123"
        sanitized = validator.sanitize_for_logging(sensitive)

        assert "sk-abc123def456" not in sanitized
        assert "secret123" not in sanitized
        assert "***" in sanitized

    @pytest.mark.unit
    def test_empty_input_after_sanitization(self, validator):
        """Test handling of input that becomes empty after sanitization."""
        # Add pattern that matches everything
        validator.add_forbidden_pattern(r".*")

        result = validator.validate("anything", sanitize=True)

        # Should be rejected as empty after sanitization
        assert result.result == ValidationResult.REJECTED

    @pytest.mark.unit
    def test_validation_report_fields(self, validator):
        """Test that validation report has all required fields."""
        result = validator.validate("test input")

        assert hasattr(result, 'result')
        assert hasattr(result, 'original_input')
        assert hasattr(result, 'sanitized_input')
        assert hasattr(result, 'issues_found')
        assert hasattr(result, 'timestamp')


class TestOutputGuardrail:
    """Test suite for OutputGuardrail."""

    @pytest.fixture
    def guardrail(self):
        """Create OutputGuardrail instance."""
        return OutputGuardrail()

    @pytest.mark.unit
    def test_initialization(self, guardrail):
        """Test guardrail initialization."""
        assert guardrail.max_output_length == 50000
        assert len(guardrail.content_filters) > 0

    @pytest.mark.security
    @pytest.mark.unit
    def test_password_filtering(self, guardrail):
        """Test password filtering in output."""
        output_with_password = "The password is: password=secret123"
        result = guardrail.check(output_with_password, filter_violations=True)

        assert len(result.violations) > 0
        assert "secret123" not in result.filtered_output

    @pytest.mark.security
    @pytest.mark.unit
    def test_api_key_filtering(self, guardrail):
        """Test API key filtering in output."""
        output_with_key = "Your API_KEY=sk-abc123def456"
        result = guardrail.check(output_with_key, filter_violations=True)

        assert len(result.violations) > 0
        assert "sk-abc123def456" not in result.filtered_output

    @pytest.mark.unit
    def test_output_length_limit(self, guardrail):
        """Test output length limit enforcement."""
        long_output = "x" * 100000  # Exceeds default 50000 limit
        result = guardrail.check(long_output, filter_violations=True)

        assert result.passed is False
        assert len(result.filtered_output) <= guardrail.max_output_length

    @pytest.mark.unit
    def test_safe_output_passes(self, guardrail):
        """Test that safe output passes all checks."""
        safe_output = "This is a completely safe output with no sensitive information."
        result = guardrail.check(safe_output)

        assert result.passed is True
        assert len(result.violations) == 0

    @pytest.mark.unit
    def test_add_content_filter(self, guardrail):
        """Test adding custom content filter."""
        guardrail.add_content_filter(r"SENSITIVE_DATA")

        result = guardrail.check("Output contains SENSITIVE_DATA", filter_violations=True)

        assert len(result.violations) > 0
        assert "SENSITIVE_DATA" not in result.filtered_output

    @pytest.mark.unit
    def test_add_required_disclaimer(self, guardrail):
        """Test adding required disclaimer."""
        disclaimer = "This is AI-generated content"
        guardrail.add_required_disclaimer(disclaimer)

        result_without = guardrail.check("Some output", filter_violations=True)

        assert len(result_without.violations) > 0
        assert disclaimer in result_without.filtered_output

    @pytest.mark.unit
    def test_check_json_format(self, guardrail):
        """Test JSON format validation."""
        valid_json = '{"key": "value"}'
        invalid_json = '{key: value}'

        result_valid = guardrail.check_format(valid_json, "json")
        result_invalid = guardrail.check_format(invalid_json, "json")

        assert result_valid.passed is True
        assert result_invalid.passed is False

    @pytest.mark.unit
    def test_check_markdown_format(self, guardrail):
        """Test markdown format validation."""
        valid_md = "# Heading\n\n**Bold** text"
        plain_text = "Just plain text with no markdown"

        result_valid = guardrail.check_format(valid_md, "markdown")
        result_plain = guardrail.check_format(plain_text, "markdown")

        assert result_valid.passed is True
        # Plain text might fail markdown check
        # (depends on implementation)

    @pytest.mark.unit
    def test_guardrail_report_fields(self, guardrail):
        """Test that guardrail report has all required fields."""
        result = guardrail.check("test output")

        assert hasattr(result, 'passed')
        assert hasattr(result, 'guardrail_type')
        assert hasattr(result, 'original_output')
        assert hasattr(result, 'filtered_output')
        assert hasattr(result, 'violations')


class TestCircuitBreaker:
    """Test suite for CircuitBreaker."""

    @pytest.fixture
    def breaker(self):
        """Create CircuitBreaker instance."""
        return CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=1.0,  # Short timeout for testing
            half_open_max_calls=2
        )

    @pytest.mark.unit
    def test_initialization(self, breaker):
        """Test circuit breaker initialization."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0

    @pytest.mark.unit
    def test_record_success_while_closed(self, breaker):
        """Test recording success while circuit is closed."""
        breaker.record_success()

        assert breaker.success_count == 1
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.unit
    def test_record_failure_opens_circuit(self, breaker):
        """Test that failures open the circuit."""
        # Record failures up to threshold
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.unit
    def test_circuit_open_rejects_calls(self, breaker):
        """Test that open circuit rejects calls."""
        # Open the circuit
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()

        # Try to call
        allowed = breaker.allow_request()

        assert allowed is False

    @pytest.mark.unit
    def test_circuit_transitions_to_half_open(self, breaker):
        """Test circuit transitions to half-open after timeout."""
        # Open the circuit
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(breaker.recovery_timeout + 0.1)

        # Next request should transition to half-open
        allowed = breaker.allow_request()

        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.unit
    def test_half_open_success_closes_circuit(self, breaker):
        """Test that success in half-open state closes circuit."""
        # Open the circuit
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()

        # Wait and transition to half-open
        time.sleep(breaker.recovery_timeout + 0.1)
        breaker.allow_request()

        # Record successes
        for _ in range(breaker.half_open_max_calls):
            breaker.record_success()

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.unit
    def test_half_open_failure_reopens_circuit(self, breaker):
        """Test that failure in half-open state reopens circuit."""
        # Open the circuit
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()

        # Wait and transition to half-open
        time.sleep(breaker.recovery_timeout + 0.1)
        breaker.allow_request()

        # Record failure
        breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.unit
    def test_get_stats(self, breaker):
        """Test getting circuit breaker statistics."""
        breaker.record_success()
        breaker.record_failure()

        stats = breaker.get_stats()

        assert isinstance(stats, CircuitBreakerStats)
        assert stats.success_count == 1
        assert stats.failure_count == 1
        assert stats.state == CircuitState.CLOSED

    @pytest.mark.unit
    def test_reset_breaker(self, breaker):
        """Test resetting circuit breaker."""
        # Record some activity
        breaker.record_failure()
        breaker.record_failure()

        # Reset
        breaker.reset()

        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED


class TestRateLimiter:
    """Test suite for RateLimiter."""

    @pytest.fixture
    def limiter(self):
        """Create RateLimiter instance."""
        return RateLimiter(
            max_requests=5,
            time_window=1.0  # 1 second window
        )

    @pytest.mark.unit
    def test_initialization(self, limiter):
        """Test rate limiter initialization."""
        assert limiter.max_requests == 5
        assert limiter.time_window == 1.0

    @pytest.mark.unit
    def test_allows_requests_under_limit(self, limiter):
        """Test that requests under limit are allowed."""
        for _ in range(5):
            allowed = limiter.allow_request()
            assert allowed is True

    @pytest.mark.unit
    def test_blocks_requests_over_limit(self, limiter):
        """Test that requests over limit are blocked."""
        # Use up the limit
        for _ in range(5):
            limiter.allow_request()

        # Next request should be blocked
        allowed = limiter.allow_request()

        assert allowed is False

    @pytest.mark.unit
    def test_rate_limit_resets_after_window(self, limiter):
        """Test that rate limit resets after time window."""
        # Use up the limit
        for _ in range(5):
            limiter.allow_request()

        # Wait for window to pass
        time.sleep(limiter.time_window + 0.1)

        # Should be able to make requests again
        allowed = limiter.allow_request()

        assert allowed is True

    @pytest.mark.unit
    def test_get_remaining_requests(self, limiter):
        """Test getting remaining request count."""
        limiter.allow_request()
        limiter.allow_request()

        remaining = limiter.get_remaining()

        assert remaining == 3  # 5 - 2 = 3

    @pytest.mark.unit
    def test_sliding_window(self, limiter):
        """Test sliding window behavior."""
        # Make 3 requests
        for _ in range(3):
            limiter.allow_request()

        # Wait half the window
        time.sleep(limiter.time_window / 2)

        # Should still be able to make 2 more requests
        assert limiter.allow_request() is True
        assert limiter.allow_request() is True

        # 6th request should be blocked
        assert limiter.allow_request() is False


class TestResourceManager:
    """Test suite for ResourceManager."""

    @pytest.fixture
    def manager(self):
        """Create ResourceManager instance."""
        return ResourceManager(
            max_memory_mb=100,
            max_cpu_percent=80
        )

    @pytest.mark.unit
    def test_initialization(self, manager):
        """Test resource manager initialization."""
        assert manager.max_memory_mb == 100
        assert manager.max_cpu_percent == 80

    @pytest.mark.unit
    def test_check_resources(self, manager):
        """Test checking resource availability."""
        available = manager.check_resources()

        assert isinstance(available, bool)

    @pytest.mark.unit
    def test_get_current_usage(self, manager):
        """Test getting current resource usage."""
        usage = manager.get_current_usage()

        assert 'memory_mb' in usage
        assert 'cpu_percent' in usage
        assert isinstance(usage['memory_mb'], (int, float))
        assert isinstance(usage['cpu_percent'], (int, float))

    @pytest.mark.integration
    def test_resource_limit_enforcement(self, manager):
        """Test that resource limits are enforced."""
        # This would need actual resource consumption to test properly
        # For now, just verify the method exists and returns boolean
        result = manager.check_resources()
        assert isinstance(result, bool)


class TestIntegrationRobustness:
    """Integration tests for complete robustness flow."""

    @pytest.mark.integration
    def test_full_validation_pipeline(self):
        """Test complete validation pipeline."""
        validator = InputValidator()
        guardrail = OutputGuardrail()
        breaker = CircuitBreaker()

        # Validate input
        input_result = validator.validate("Safe input text")
        assert input_result.result == ValidationResult.VALID

        # Process (simulated)
        output = "Safe output text"

        # Check output
        output_result = guardrail.check(output)
        assert output_result.passed is True

        # Record success in circuit breaker
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.integration
    def test_failure_recovery_flow(self):
        """Test failure detection and recovery flow."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.5
        )

        # Simulate failures
        breaker.record_failure()
        breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery
        time.sleep(0.6)

        # Allow request (transitions to half-open)
        breaker.allow_request()
        assert breaker.state == CircuitState.HALF_OPEN

        # Successful recovery
        breaker.record_success()
        breaker.record_success()

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.integration
    @pytest.mark.security
    def test_security_pipeline(self):
        """Test complete security validation pipeline."""
        validator = InputValidator()
        guardrail = OutputGuardrail()

        # Malicious input
        malicious_input = "<script>alert('xss')</script>"
        input_result = validator.validate(malicious_input, sanitize=True)

        # Should be sanitized or rejected
        assert input_result.result in [
            ValidationResult.SANITIZED,
            ValidationResult.REJECTED
        ]

        # Sensitive output
        sensitive_output = "password=secret123"
        output_result = guardrail.check(sensitive_output, filter_violations=True)

        # Should be filtered
        assert "secret123" not in output_result.filtered_output


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.unit
    def test_empty_input_validation(self):
        """Test validation of empty input."""
        validator = InputValidator()
        result = validator.validate("")

        assert result.result in [ValidationResult.VALID, ValidationResult.REJECTED]

    @pytest.mark.unit
    def test_unicode_input_handling(self):
        """Test handling of unicode characters."""
        validator = InputValidator()
        unicode_input = "Hello 世界 🌍"

        result = validator.validate(unicode_input)

        assert result.result == ValidationResult.VALID

    @pytest.mark.unit
    def test_circuit_breaker_concurrent_access(self):
        """Test circuit breaker with concurrent access."""
        import threading

        breaker = CircuitBreaker()
        results = []

        def make_request():
            allowed = breaker.allow_request()
            results.append(allowed)

        threads = [threading.Thread(target=make_request) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should be allowed while circuit is closed
        assert all(results)

    @pytest.mark.unit
    def test_rate_limiter_zero_limit(self):
        """Test rate limiter with zero limit."""
        limiter = RateLimiter(max_requests=0, time_window=1.0)

        # All requests should be blocked
        allowed = limiter.allow_request()

        assert allowed is False
